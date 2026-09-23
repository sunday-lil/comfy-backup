# -*- coding: utf-8 -*-
"""dump 编码后的 prompt token ids 验证正确性"""
import sys
sys.path.insert(0, r"D:\fish-speech-main")
from fish_speech.tokenizer import FishTokenizer
from fish_speech.conversation import Conversation, Message
from fish_speech.content_sequence import TextPart

t = FishTokenizer(r"D:\fish-speech-main\checkpoints\openaudio-s1-mini")
conv = Conversation()
conv.append(Message(role="system", parts=[TextPart(text="convert the provided text to speech", cal_loss=False)], cal_loss=False))
conv.append(Message(role="user", parts=[TextPart(text="你好。", cal_loss=False)], cal_loss=False))
conv.append(Message(role="assistant", parts=[], cal_loss=False, modality="voice", add_im_end=False))
enc, audio_masks, audio_parts = conv.encode_for_inference(t, num_codebooks=10)
print("shape:", enc.shape)
ids = enc[0].tolist()
print("ids:", ids)
print("decoded:", repr(t.decode(ids)))
# 关键 id 参照: im_start=151646, im_end=151647, voice=151653, semantic_begin=151658
