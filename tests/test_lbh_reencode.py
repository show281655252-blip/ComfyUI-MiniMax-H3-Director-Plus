"""Run with ComfyUI's Python; no model weights or server needed."""
import importlib.util
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root.parent.parent))
import torch
spec = importlib.util.spec_from_file_location('director_lbh', root / 'engine/director_lbh.py')
lbh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lbh)


class PixelVAE:
    def __init__(self):
        self.decodes = 0

    def decode(self, latent):
        self.decodes += 1
        return latent[0, :3].permute(1, 2, 3, 0).repeat_interleave(16, 1).repeat_interleave(16, 2)

    def encode(self, pixels):
        return pixels[:, ::16, ::16, :].permute(3, 0, 1, 2).unsqueeze(0).repeat(1, 8, 1, 1, 1)


class ReencodeTests(unittest.TestCase):
    def test_original_source_and_audio_preserved(self):
        vae = PixelVAE()
        latent = torch.zeros(1, 24, 1, 54, 40)
        source = torch.ones(1, 128, 96, 3)
        audio = torch.randn(1, 32, 2, 10)
        cond = [[torch.zeros(1), {'minimax_refs': [
            {'kind':'image', 'latent':latent, 'latent_h':54, 'latent_w':40,
             '_director_source_pixels':source}, {'kind':'audio', 'audio_latent':audio}],
            'minimax_keyframes':[{'resolved_frame_index':0, 'latent':latent}]}]]
        result = lbh.resize_conditioning(cond, 640, 864, 960, 1280, vae, {'first_frame':source})
        meta = result[0][1]
        self.assertEqual(vae.decodes, 0)
        for block in (meta['minimax_refs'][0], meta['minimax_keyframes'][0]):
            self.assertEqual(tuple(block['latent'].shape), (1,24,1,80,60))
            self.assertTrue(torch.allclose(block['latent'], torch.ones_like(block['latent'])))
        self.assertIs(meta['minimax_refs'][1]['audio_latent'], audio)
        self.assertEqual(meta['minimax_keyframes'][0]['resolved_frame_index'], 0)
        self.assertIs(cond[0][1]['minimax_refs'][0]['latent'], latent)

    def test_fallback_temporal_layout_and_noop(self):
        vae = PixelVAE()
        latent = torch.zeros(1,24,5,18,16)
        result = lbh.reencode_visual(latent, 24, 28, vae)
        self.assertEqual(tuple(result.shape), (1,24,5,28,24))
        self.assertEqual(vae.decodes, 1)
        self.assertIs(lbh.reencode_visual(result, 24, 28, vae), result)
        self.assertEqual(vae.decodes, 1)


if __name__ == '__main__':
    unittest.main()
