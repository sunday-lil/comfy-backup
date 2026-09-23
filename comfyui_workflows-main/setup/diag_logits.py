# -*- coding: utf-8 -*-
"""诊断：加载 S1-mini，跑一次 prefill，dump 主流 top-10 logits"""
import sys
sys.path.insert(0, r"D:\fish-speech-main")
import torch
from fish_speech.tokenizer import FishTokenizer, IM_END_TOKEN
from fish_speech.conversation import Conversation, Message
from fish_speech.content_sequence import TextPart
from fish_speech.models.text2semantic.llama import DualARTransformer

CKPT = r"D:\fish-speech-main\checkpoints\openaudio-s1-mini"
device, precision = "cuda", torch.bfloat16

print("loading model...")
model = DualARTransformer.from_pretrained(CKPT, load_weights=True)
model = model.to(device=device, dtype=precision).eval()
tokenizer = model.tokenizer
print("semantic range in config:", model.config.semantic_begin_id, model.config.semantic_end_id)

conv = Conversation()
conv.append(Message(role="system", parts=[TextPart(text="convert the provided text to speech", cal_loss=False)], cal_loss=False))
conv.append(Message(role="user", parts=[TextPart(text="你好，今天天气真不错。", cal_loss=False)], cal_loss=False))
conv.append(Message(role="assistant", parts=[], cal_loss=False, modality="voice", add_im_end=False))
values, _, _ = conv.encode_for_inference(tokenizer, num_codebooks=model.config.num_codebooks)
prompt = values.to(device)
print("prompt shape:", prompt.shape)

# setup cache & prefill
with torch.device(device):
    model.setup_caches(max_batch_size=1, max_seq_len=model.config.max_seq_len, dtype=precision)
input_pos = torch.arange(0, prompt.size(1), device=device)
with torch.inference_mode():
    fr = model.forward_generate(prompt.view(1, model.config.num_codebooks + 1, -1), input_pos)
logits = fr.logits  # (1, 1, vocab)
print("logits nan?", torch.isnan(logits).any().item(), "inf?", torch.isinf(logits).any().item())
main = logits[0, -1].float()
top = torch.topk(main, 10)
im_end_id = tokenizer.get_token_id(IM_END_TOKEN)
print("im_end_id:", im_end_id, "logit:", main[im_end_id].item())
for v, i in zip(top.values.tolist(), top.indices.tolist()):
    tag = " <== im_end" if i == im_end_id else (" (semantic)" if model.config.semantic_begin_id <= i <= model.config.semantic_end_id else "")
    print(f"  id={i} logit={v:.3f} token={tokenizer.decode([i])!r}{tag}")
print("mem:", torch.cuda.max_memory_reserved() / 1e9, "GB")
