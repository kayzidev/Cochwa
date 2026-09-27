"""Audit reproductible : fixtures temporaires, HTTP et processus simulés.
Ce sont des reproductions de défauts actuels, pas des tests de conformité.
Usage : PYTHONPATH=. python3 audit/probe.py [--gui]
"""
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from romget.api import ia, redump
from romget.config import Config, ProviderConfig
from romget.providers.ia_redump import IARedumpProvider

class Response:
    status_code = 200
    headers = {'content-length': '6'}
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def raise_for_status(self): pass
    def iter_content(self, **kw): yield b'abcdef'

out = {}
with tempfile.TemporaryDirectory(prefix='romget-audit-') as tmp:
    base = Path(tmp)
    dest = base/'partial.iso'
    dest.write_bytes(b'abc')
    with patch.object(ia.requests, 'get', return_value=Response()):
        ok = ia.download_file('fixture', 'partial.iso', dest, 6)
    out['resume_200'] = {'success': ok, 'bytes': dest.read_text(), 'expected': 'abcdef'}
    dest.write_bytes(b'XXXXXX')
    with patch.object(ia.requests, 'get') as get:
        ok = ia.download_file('fixture','partial.iso',dest,6)
    out['same_size_wrong_content'] = {'success':ok,'network_called':get.called}
    short = base/'short.iso'
    with patch.object(ia.requests, 'get', return_value=Response()):
        ok = ia.download_file('fixture','short.iso',short,10)
    out['wrong_final_size'] = {'success':ok,'actual':short.stat().st_size,'expected':10}
    cache = base/'redump.json'
    cache.write_text(json.dumps({'saved_at':0,'md5_to_title':{'abc':'Fixture'},'titles':['Fixture']}))
    df = redump.RedumpDatfile()
    with patch.object(redump,'CACHE_FILE',cache), patch.object(df,'_download_and_parse',side_effect=OSError('offline fixture')):
        out['expired_cache_fallback'] = df.load()
    game_dir = base/'game'; game_dir.mkdir()
    for n in ['disc1.iso','disc2.iso','unrelated.bin']:
        (game_dir/n).write_bytes(b'fixture')
    provider = IARedumpProvider(ProviderConfig(name='ia_redump',options={'cache_dir':str(base/'cache')}))
    def fake_chd(cmd, **kw):
        Path(cmd[cmd.index('-o')+1]).write_bytes(b'fake chd')
        return SimpleNamespace(returncode=0)
    with patch('shutil.which',return_value='/fixture/chdman'),patch('subprocess.run',side_effect=fake_chd):
        provider._convert_to_chd(game_dir)
    out['chd_remaining_files'] = sorted(p.name for p in game_dir.iterdir())
    download_dir = base/'destination'; download_dir.mkdir()
    with patch.object(ia.requests,'get',return_value=Response()):
        provider._download_file('fixture','../outside.iso',download_dir,6)
    out['path_escape'] = (base/'outside.iso').exists()
    with patch.object(Config,'_write_default'):
        try: Config.load(base/'custom-missing.toml')
        except Exception as e: out['custom_config_missing'] = type(e).__name__
    df = SimpleNamespace(lookup_title_by_md5=lambda x:None,is_ps2_title=lambda x:True)
    files=[{'name':'fixture.iso','size':600*1024**2,'md5':'not-a-redump-hash'}]
    with patch.object(ia,'_search_ia',return_value=[('fixture','Known title')]),patch.object(ia,'get_datfile',return_value=df),patch.object(ia,'_fetch_item_files',return_value=(files,600*1024**2,'fixture.iso')):
        out['title_only_marked_verified'] = ia.search_ps2('Known',ps2_only=True)[0].is_ps2
    if '--gui' in sys.argv:
        from romget.gui.app import RomgetApp
        from romget.gui.tab_search import SearchTab
        from romget.gui.tab_gamelist import GameListTab
        from romget.gui.tab_library import LibraryTab
        from romget.api.ia import IAGame
        import tkinter as tk
        # Suspend only external work; exercise actual widgets and callbacks.
        with patch('threading.Thread.start'),patch.object(RomgetApp,'_preload_datfile'):
            app = RomgetApp(Config(ps2_dir=Path('/mnt/Backup-ROMs/Emulateurs/PS2/games')))
            try:
                app.root.update()
                out['gui_tabs'] = [app.notebook.tab(t,'text') for t in app.notebook.tabs()]
                out['gui_library_cards'] = len(app.tab_library._cards)
                app.notebook.select(app.tab_library); app.root.update()
                out['gui_library_geometry'] = {'canvas':app.tab_library.canvas.winfo_width(),'grid':app.tab_library.grid_frame.winfo_reqwidth()}
                game = IAGame('fixture','Fixture','Fixture',[],None,600*1024**2,False)
                app.tab_search._show_results('old',[game])
                app.tab_search._show_results('new',[game])
                out['gui_overlapping_result_cards'] = len(app.tab_search._cards)
                app.tab_recommended._add_card('Fixture',game)
                card = app.tab_recommended._cards['Fixture']
                out['gui_unverified_labels'] = [w.cget('text') for w in card.winfo_children() if isinstance(w, __import__('tkinter').ttk.Label)]
                callbacks=[]
                fake = SimpleNamespace(ps2_only=True,status_var=SimpleNamespace(set=lambda value:None),after=lambda delay, cb:callbacks.append(cb))
                with patch('romget.gui.tab_search.search_ps2',side_effect=RuntimeError('fixture')):
                    SearchTab._search_worker(fake,'fixture')
                try: callbacks[0]()
                except Exception as e: out['gui_error_callback'] = type(e).__name__ + ': ' + str(e)
                app.config.ps2_dir=base
                (base/'Empty game').mkdir()
                out['gui_empty_directory_installed'] = app.is_installed('Empty game')
                # Restore real library before measuring minimum window size.
                app.config.ps2_dir=Path('/mnt/Backup-ROMs/Emulateurs/PS2/games')
                app.root.geometry('900x600'); app.root.update()
                out['gui_minimum_geometry'] = {'canvas':app.tab_library.canvas.winfo_width(),'grid':app.tab_library.grid_frame.winfo_reqwidth()}
                out['gui_mousewheel_binding'] = app.tab_library.canvas.bind('<MouseWheel>')
                # Capture only this test window, if X11 capture is available.
                try:
                    from PIL import ImageGrab
                    x,y=app.root.winfo_rootx(),app.root.winfo_rooty()
                    ImageGrab.grab(bbox=(x,y,x+app.root.winfo_width(),y+app.root.winfo_height()),xdisplay=app.root.winfo_screen()).save('audit/gui-library.png')
                    out['gui_capture']='audit/gui-library.png'
                except Exception as e: out['gui_capture_error']=type(e).__name__+': '+str(e)
            finally: app.root.destroy()
print(json.dumps(out,indent=2,ensure_ascii=False))
Path('audit/results' + ('-gui' if '--gui' in sys.argv else '') + '.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
