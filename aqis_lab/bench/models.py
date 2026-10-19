"""Sprint 1 model wrappers: one small class per model family, all heavy imports inside the wrapper.

CAPABILITIES:
  CAP-S1-016: load() returns a Transcriber for a model of s1.yaml: Whisper large-v3 and turbo, Granite Speech, Cohere
    Transcribe and Voxtral Realtime through transformers; Parakeet TDT v2 and Parakeet Unified through NeMo ASR;
    Canary-Qwen through NeMo SALM; Qwen3-ASR through the qwen-asr package. Each loads once at the resolved revision, takes
    16 kHz float32 clips, decodes greedily with the card's own settings, forces English, uses no keywords or context, and
    reports library versions, dtype, parameter count and peak GPU memory. prepare() does untimed work (writing wav files,
    padding tensors) so run() is what the runner times. They need a GPU and the model, so the Colab smoke run checks them;
    they have no unit tests.
INPUTS AND OUTPUTS: a model name, its config block, a revision SHA and a dtype in; a Transcriber out whose
  transcribe(list of float32 arrays) returns one text per clip; ModelError.
CONTRACTS: brief section 4 ("How to run every model") and the Hugging Face cards checked on 17 Oct 2026.
INVARIANTS:
  - Importing this module imports no ML library; each wrapper imports its own stack when it is built.
  - The model is loaded at `revision`, never at a moving branch.
  - No keyword, prompt or context is added beyond the card's own prompt text in the config.
NOT IN SCOPE:
  - Timing, batching and file writing (aqis_lab/bench/run.py); streaming (Sprint 2).
CHANGE LOG:
  2026-10-17 WP-1.1 created.
"""
import gc
import importlib.metadata
import json
import logging
import shutil
import tempfile
from pathlib import Path

from aqis_lab.bench import lib

SR = 16000
LIBRARIES = ("torch", "transformers", "nemo_toolkit", "qwen-asr", "mistral_common", "huggingface_hub", "accelerate",
             "soundfile", "numpy", "safetensors", "tokenizers")
DTYPES = ("bf16", "fp16", "fp32")


class ModelError(RuntimeError):
    """A model cannot be loaded or run as the brief and its card say."""


def _torch_dtype(name):
    torch = lib("torch")
    if name not in DTYPES:
        raise ModelError(f"dtype must be one of {DTYPES}, got {name!r}")
    if name == "bf16" and not torch.cuda.is_bf16_supported():
        raise ModelError("this GPU has no bf16 (a T4); pass --dtype fp16 for a NeMo model and record it")
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[name]


def ensure_validation_ds(model, omegaconf=None):
    """Give a NeMo model an empty validation_ds when its config has none.

    EncDecRNNTBPEModel.transcribe reads cfg.validation_ds (rnnt_bpe_models.py) and crashes with
    "'NoneType' object has no attribute 'get'" when it is None, as in nvidia/parakeet-unified-en-0.6b."""
    cfg = getattr(model, "cfg", None)
    if cfg is not None and getattr(cfg, "validation_ds", None) is None:
        omegaconf = omegaconf or lib("omegaconf")
        with omegaconf.open_dict(cfg):
            cfg.validation_ds = omegaconf.OmegaConf.create({})


def add_torchao_symbols(functional):
    """Guard for torch < 2.11: add two names that torchao 0.15+ imports from torch.nn.functional.

    The fix is the lock: s1-nemo.in pins torchao<0.15, so transformers never imports torchao (the second
    missing name, SwizzleType, showed on the 19 Oct 2026 Colab run that a name-by-name shim cannot keep up). This
    stays as a guard for the two names it covers; nothing here is quantized. Returns the names that were added."""
    added = []
    if not hasattr(functional, "ScalingType"):
        functional.ScalingType = type("ScalingType", (), {})
        added.append("ScalingType")
    if not hasattr(functional, "scaled_grouped_mm"):
        functional.scaled_grouped_mm = None
        added.append("scaled_grouped_mm")
    return added


class Transcriber:
    """Base class: subclasses set self.model (or self.module) and implement prepare/run."""

    dtype = ""
    decoding = ""
    warmed = False
    module = None

    def prepare(self, audios):
        return audios

    def run(self, prepared):
        raise ModelError(f"{type(self).__name__} does not define run")

    def release(self, prepared):
        return None

    def transcribe(self, audios):
        prepared = self.prepare(audios)
        try:
            return self.run(prepared)
        finally:
            self.release(prepared)

    def sync(self):
        torch = lib("torch")
        if torch.cuda.is_available():
            torch.cuda.synchronize()

    def versions(self):
        found = {}
        for name in LIBRARIES:
            try:
                found[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                continue
        return found

    def info(self):
        torch = lib("torch")
        module = self.module if self.module is not None else getattr(self, "model", None)
        params = sum(p.numel() for p in module.parameters()) if hasattr(module, "parameters") else None
        peak = torch.cuda.max_memory_allocated() / 2 ** 20 if torch.cuda.is_available() else None
        return {"params": params, "peak_gpu_mem_mib": peak, "dtype": self.dtype, "decoding": self.decoding,
                "versions": self.versions()}

    def close(self):
        torch = lib("torch")
        for attr in ("model", "module", "processor"):
            if hasattr(self, attr):
                setattr(self, attr, None)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# ---- transformers ---------------------------------------------------------------------------------------------
class WhisperHF(Transcriber):
    decoding = "greedy (do_sample=False, num_beams=1), language forced, task transcribe, max_new_tokens 440"

    def __init__(self, name, cfg, revision, dtype):
        transformers = lib("transformers")
        self.dtype = dtype or cfg.get("dtype", "bf16")
        self.language = cfg["language"]
        self.processor = transformers.AutoProcessor.from_pretrained(cfg["hf"], revision=revision)
        self.model = transformers.AutoModelForSpeechSeq2Seq.from_pretrained(
            cfg["hf"], revision=revision, dtype=_torch_dtype(self.dtype)).to("cuda").eval()
        self.torch = lib("torch")

    def run(self, audios):
        feats = self.processor(audios, sampling_rate=SR, return_tensors="pt", return_attention_mask=True).to("cuda")
        with self.torch.inference_mode():
            ids = self.model.generate(input_features=feats.input_features.to(self.model.dtype),
                                      attention_mask=feats.attention_mask, language=self.language, task="transcribe",
                                      do_sample=False, num_beams=1, max_new_tokens=440)
        return [t.strip() for t in self.processor.batch_decode(ids, skip_special_tokens=True)]


class GraniteHF(Transcriber):
    decoding = "greedy (do_sample=False, num_beams=1), the card's prompt, max_new_tokens 256"

    def __init__(self, name, cfg, revision, dtype):
        transformers = lib("transformers")
        self.dtype = dtype or cfg.get("dtype", "bf16")
        self.processor = transformers.AutoProcessor.from_pretrained(cfg["hf"], revision=revision)
        self.tokenizer = self.processor.tokenizer
        self.tokenizer.padding_side = "left"
        self.model = transformers.AutoModelForSpeechSeq2Seq.from_pretrained(
            cfg["hf"], revision=revision, device_map="cuda", dtype=_torch_dtype(self.dtype)).eval()
        self.prompt = self.tokenizer.apply_chat_template([{"role": "user", "content": cfg["prompt"]}], tokenize=False,
                                                         add_generation_prompt=True)
        self.torch = lib("torch")

    def run(self, audios):
        wavs = [self.torch.from_numpy(a)[None, :] for a in audios]
        inputs = self.processor([self.prompt] * len(wavs), wavs, device="cuda", return_tensors="pt",
                                padding=True).to("cuda")
        with self.torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=256, do_sample=False, num_beams=1)
        new = out[:, inputs["input_ids"].shape[-1]:]
        return [t.strip() for t in self.tokenizer.batch_decode(new, add_special_tokens=False, skip_special_tokens=True)]


class CohereHF(Transcriber):
    decoding = "greedy (generate defaults), language forced, punctuation on (card default), max_new_tokens 440"

    def __init__(self, name, cfg, revision, dtype):
        transformers = lib("transformers")
        self.dtype = dtype or cfg.get("dtype", "bf16")
        self.language = cfg["language"]
        self.processor = transformers.AutoProcessor.from_pretrained(cfg["hf"], revision=revision)
        self.model = transformers.CohereAsrForConditionalGeneration.from_pretrained(
            cfg["hf"], revision=revision, dtype=_torch_dtype(self.dtype)).to("cuda").eval()
        self.torch = lib("torch")

    def run(self, audios):
        inputs = self.processor(audios, sampling_rate=SR, return_tensors="pt", language=self.language)
        chunk_index = inputs.get("audio_chunk_index")
        inputs.to(self.model.device, dtype=self.model.dtype)
        with self.torch.inference_mode():
            outputs = self.model.generate(**inputs, max_new_tokens=440)
        texts = self.processor.decode(outputs, skip_special_tokens=True, audio_chunk_index=chunk_index,
                                      language=self.language)
        return [t.strip() for t in texts]


class VoxtralHF(Transcriber):
    decoding = "greedy (generate defaults), one clip at a time (the card's transformers example is single-clip)"

    def __init__(self, name, cfg, revision, dtype):
        transformers = lib("transformers")
        hub = lib("huggingface_hub")
        self.dtype = dtype or cfg.get("dtype", "bf16")
        delay = self._delay_ms(json.loads(Path(hub.hf_hub_download(cfg["hf"], "tekken.json", revision=revision)).read_text(
            encoding="utf-8")))
        if delay != cfg["delay_ms"]:
            raise ModelError(f"tekken.json at {revision[:10]} sets transcription_delay_ms {delay}, the config asks for "
                             f"{cfg['delay_ms']}")
        self.delay_ms = delay
        self.processor = transformers.AutoProcessor.from_pretrained(cfg["hf"], revision=revision)
        self.model = transformers.VoxtralRealtimeForConditionalGeneration.from_pretrained(
            cfg["hf"], revision=revision, dtype=_torch_dtype(self.dtype)).to("cuda").eval()
        self.decoding += f"; transcription_delay_ms {delay} (the card's recommended setting)"
        self.torch = lib("torch")

    @staticmethod
    def _delay_ms(node):
        if isinstance(node, dict):
            if "transcription_delay_ms" in node:
                return node["transcription_delay_ms"]
            for value in node.values():
                found = VoxtralHF._delay_ms(value)
                if found is not None:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = VoxtralHF._delay_ms(value)
                if found is not None:
                    return found
        return None

    def run(self, audios):
        texts = []
        for audio in audios:
            inputs = self.processor(audio, return_tensors="pt").to(self.model.device, dtype=self.model.dtype)
            with self.torch.inference_mode():
                out = self.model.generate(**inputs)
            texts.append(self.processor.batch_decode(out, skip_special_tokens=True)[0].strip())
        return texts


# ---- NeMo -----------------------------------------------------------------------------------------------------
class NemoAsr(Transcriber):
    decoding = "the model's own greedy transducer decoding (transcribe defaults)"

    def __init__(self, name, cfg, revision, dtype):
        nemo_asr = lib("nemo.collections.asr")
        logging.getLogger("nemo_logger").setLevel(logging.ERROR)
        self.dtype = dtype or cfg.get("dtype", "bf16")
        self.autocast = None if self.dtype == "fp32" else _torch_dtype(self.dtype)
        folder = lib("huggingface_hub").snapshot_download(cfg["hf"], revision=revision)
        files = sorted(Path(folder).glob("*.nemo"))
        if len(files) != 1:
            raise ModelError(f"{cfg['hf']}@{revision[:10]} holds {len(files)} .nemo files, expected one")
        self.model = nemo_asr.models.ASRModel.restore_from(str(files[0])).to("cuda").eval()
        ensure_validation_ds(self.model)
        self.batch = cfg["batch"]
        self.scratch = Path(tempfile.mkdtemp(prefix="s1_nemo_"))
        self.torch = lib("torch")
        self.counter = 0

    def prepare(self, audios):
        sf = lib("soundfile")
        self.counter += 1
        paths = []
        for i, audio in enumerate(audios):
            path = self.scratch / f"{self.counter}_{i}.wav"
            sf.write(str(path), audio, SR, subtype="PCM_16")
            paths.append(str(path))
        return paths

    def release(self, prepared):
        for path in prepared:
            Path(path).unlink(missing_ok=True)

    def run(self, paths):
        with self.torch.inference_mode(), self.torch.autocast("cuda", dtype=self.autocast, enabled=self.autocast is not None):
            out = self.model.transcribe(paths, batch_size=len(paths))
        if isinstance(out, tuple):
            out = out[0]
        return [(h.text if hasattr(h, "text") else h).strip() for h in out]

    def close(self):
        shutil.rmtree(self.scratch, ignore_errors=True)
        super().close()


class NemoSalm(Transcriber):
    decoding = "SALM.generate, the card's prompt, greedy (generate defaults), max_new_tokens 256"

    def __init__(self, name, cfg, revision, dtype):
        add_torchao_symbols(lib("torch.nn.functional"))
        salm = lib("nemo.collections.speechlm2.models").SALM
        logging.getLogger("nemo_logger").setLevel(logging.ERROR)
        self.dtype = dtype or cfg.get("dtype", "bf16")
        self.autocast = None if self.dtype == "fp32" else _torch_dtype(self.dtype)
        folder = lib("huggingface_hub").snapshot_download(cfg["hf"], revision=revision)
        self.model = salm.from_pretrained(folder).to("cuda").eval()
        self.prompt = cfg["prompt"].replace("{audio}", self.model.audio_locator_tag)
        self.torch = lib("torch")

    def prepare(self, audios):
        longest = max(len(a) for a in audios)
        batch = self.torch.zeros(len(audios), longest)
        for i, audio in enumerate(audios):
            batch[i, :len(audio)] = self.torch.from_numpy(audio)
        lens = self.torch.tensor([len(a) for a in audios])
        return batch.to("cuda"), lens.to("cuda")

    def run(self, prepared):
        batch, lens = prepared
        prompts = [[{"role": "user", "content": self.prompt}] for _ in range(len(batch))]
        with self.torch.inference_mode(), self.torch.autocast("cuda", dtype=self.autocast, enabled=self.autocast is not None):
            ids = self.model.generate(prompts=prompts, audios=batch, audio_lens=lens, max_new_tokens=256)
        return [self.model.tokenizer.ids_to_text(row.cpu()).strip() for row in ids]


# ---- qwen-asr -------------------------------------------------------------------------------------------------
class QwenAsr(Transcriber):
    decoding = "qwen-asr transformers backend, language forced, max_new_tokens 256 (the card's example)"

    def __init__(self, name, cfg, revision, dtype):
        qwen_asr = lib("qwen_asr")
        folder = lib("huggingface_hub").snapshot_download(cfg["hf"], revision=revision)
        self.dtype = dtype or cfg.get("dtype", "bf16")
        self.language = cfg["language"]
        self.model = qwen_asr.Qwen3ASRModel.from_pretrained(folder,
                                                   dtype=_torch_dtype(self.dtype), device_map="cuda:0",
                                                   max_inference_batch_size=cfg["batch"], max_new_tokens=256)

    def info(self):
        self.module = getattr(self.model, "model", None)
        return super().info()

    def run(self, audios):
        results = self.model.transcribe(audio=[(a, SR) for a in audios], language=[self.language] * len(audios))
        return [r.text.strip() for r in results]


FAMILIES = {
    "whisper-large-v3": WhisperHF, "whisper-large-v3-turbo": WhisperHF, "granite-speech-4.1-2b": GraniteHF,
    "cohere-transcribe-2b": CohereHF, "voxtral-realtime-4b": VoxtralHF, "parakeet-tdt-0.6b-v2": NemoAsr,
    "parakeet-unified-0.6b": NemoAsr, "canary-qwen-2.5b": NemoSalm, "qwen3-asr-1.7b": QwenAsr,
}


def load(name, cfg, revision, dtype=None):
    if name not in FAMILIES:
        raise ModelError(f"no wrapper for model {name!r}; wrappers exist for {', '.join(FAMILIES)}")
    return FAMILIES[name](name, cfg, revision, dtype)
