# -*- coding: utf-8 -*-
import hashlib, io, os
SEAL = r'c:\Users\bonob\OneDrive\ドキュメント\AntiGlavity\ネオ秘書くん\assets\dot\seal'
for name in ('tea_pillar_1.png', 'tea_pillar_2.png', 'idle_1.png', 'idle_2.png'):
    p = os.path.join(SEAL, name)
    data = open(p, 'rb').read()
    mt = os.path.getmtime(p)
    import datetime
    print(name, 'bytes=', len(data), 'sha1=', hashlib.sha1(data).hexdigest()[:12], 'mtime=', datetime.datetime.fromtimestamp(mt).strftime('%H:%M:%S'))