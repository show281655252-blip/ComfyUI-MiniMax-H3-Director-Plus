"""CPU-only cache identity regression checks, without loading ComfyUI/models."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def function(file, name, namespace):
    tree = ast.parse((ROOT/'engine'/file).read_text(encoding='utf8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), file, 'exec'), namespace)
    return namespace[name]


class CacheTests(unittest.TestCase):
    def setUp(self):
        env = dict(copy=copy, hashlib=hashlib, json=json)
        self.prepare = function('director_long.py', 'prepare_state', env)
        self.owner = function('director_project.py', 'project_owner', {
            **env, 'extender': SimpleNamespace(_manual_effective_resolution=lambda w,h:(w,h))})
        self.state = {'project_id':'fixed', 'context_length':'22', 'start_mode':'new',
                      'clips':[{'id':'one','validated':True,'prompt':'fixed'}]}
        self.widgets = {'width':640,'height':864}

    def test_disabled_preserves_old_owner(self):
        old = 'director_fixed_' + hashlib.sha256(json.dumps([None,640,864,'22']).encode()).hexdigest()[:12]
        for extras in ({}, {'h3_refine':None}):
            state = {**self.state, **extras, 'cache_owner':old}
            out,_ = self.prepare({**self.widgets, 'long_video':state})
            self.assertEqual(out['cache_owner'],old)
            self.assertTrue(out['clips'][0]['validated'])
            self.assertEqual(self.owner(state,self.widgets),old)

    def test_enabled_config_and_project_restore_agree(self):
        owners = set()
        for steps,pack in ((2,'a'),(3,'a'),(2,'b')):
            state = {**self.state,'h3_refine':{'version':1,'steps':steps,'pack_hash':pack},
                     'lbh':{'scale':1.5},'audio_regen':{'steps':30}}
            out,_ = self.prepare({**self.widgets, 'long_video':state})
            self.assertEqual(out['cache_owner'],self.owner(state,self.widgets))
            self.assertFalse(out['clips'][0]['validated'])
            self.assertTrue(state['clips'][0]['validated'])
            owners.add(out['cache_owner'])
        self.assertEqual(len(owners),3)


class AdapterTests(unittest.TestCase):
    def test_disabled_needs_no_pack(self):
        settings = function('director_refine.py','settings',{})
        with patch.dict('sys.modules', {'nodes':SimpleNamespace(NODE_CLASS_MAPPINGS={})}):
            self.assertIsNone(settings(False))
            with self.assertRaisesRegex(ValueError,'install ComfyUI-H3-Refine'):
                settings(True)

    def test_conditioning_grid_pin_and_audio_guard(self):
        import torch
        video = torch.zeros(1,24,12,8,10)
        audio = torch.zeros(1,32,2,40)
        class Nested:
            def __init__(self,parts):self.parts=parts
            def unbind(self):return self.parts
        def latent(v,a):return {'samples':Nested((v,a))}
        called={}
        class Pack:
            def refine(self,**kw):
                called.update(kw)
                return (latent(video+1,audio),)
        def resize(cond,bw,bh,tw,th,vae):
            self.assertEqual((bw,bh,tw,th),(128,128,160,128))
            return 'resized base'
        fn=function('director_refine.py','refine',{'director_lbh':SimpleNamespace(resize_conditioning=resize)})
        config={'steps':2,'sampler':'res_multistep'}
        with patch.dict('sys.modules',{'nodes':SimpleNamespace(NODE_CLASS_MAPPINGS={'H3RefinePass':Pack})}):
            fn(None,'base',latent(video,audio),128,128,None,123,[1,.8,0],22,config)
            self.assertEqual(called['conditioning'],'resized base')
            self.assertEqual(called['pin_frames'],22)
            self.assertEqual(called['refine_audio'],'freeze')
            self.assertEqual(called['refine_align'],'hop_tail')
            Pack.refine=lambda self,**kw:(latent(video,audio+1),)
            result=fn(None,'base',latent(video,audio),128,128,None,123,[1,.8,0],0,config)
            self.assertIs(result['samples'].unbind()[1],audio)
            Pack.refine=lambda self,**kw:(latent(video[:,:,:,:4],audio),)
            with self.assertRaisesRegex(ValueError,'latent layout changed'):
                fn(None,'base',latent(video,audio),128,128,None,123,[1,.8,0],0,config)


if __name__ == '__main__':
    unittest.main()
