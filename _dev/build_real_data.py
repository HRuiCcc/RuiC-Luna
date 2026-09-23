#!/usr/bin/env python3
"""
把 NASA 的真实月面数据转成本项目着色器直接读取的格式。

数据源（公有领域，建议署名 NASA SVS / LRO）：
  · 高程：LOLA 激光测高，16 像素/度，5760×2880，16bit
      https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/ldem_16_uint.tif
  · 反照率：LROC WAC 全球底图（poles 版，0° 经度居中），8192×4096
      https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_8k.tif

输出（写入 ../data/）：
  moon_h.bin   5760×2880 RG8 打包的 16bit 归一化高程（可直接当纹理上传）
  moon_a.bin   4096×2048 RG8 打包的 16bit 反照率（已含烘焙环境光遮蔽）
  meta.json    {hMin, hMax, w, h, aw, ah, src}

依赖：curl、ffmpeg、numpy
用法：python3 build_real_data.py [--res 5760x2880] [--no-download]
"""
import os, sys, json, subprocess, argparse, urllib.request
import numpy as np

BASE = 'https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/'
SRC_H = BASE + 'ldem_16_uint.tif'
SRC_A = BASE + 'lroc_color_poles_8k.tif'
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache')
OUT = os.path.join(HERE, '..', 'data')
R_MEAN_M = 1737400.0          # 参考球面半径（米）
R_DATUM_M = 1747400.0         # CGI Moon Kit 16bit 位移图的基准半径（米，最高点）

ap = argparse.ArgumentParser()
ap.add_argument('--no-download', action='store_true')
ap.add_argument('--keep-cache', action='store_true')
a = ap.parse_args()
os.makedirs(CACHE, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def fetch(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 100000:
        print('· 已缓存', os.path.basename(path))
        return path
    print('· 下载', url)
    tmp = path + '.part'
    with urllib.request.urlopen(url) as r, open(tmp, 'wb') as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(tmp, path)
    print('  完成 %,d 字节' % os.path.getsize(path))
    return path


def to_raw(tif, pix_fmt, out, shape, dtype=np.uint8):
    if not os.path.exists(out):
        print('· 转换', os.path.basename(tif), '→', os.path.basename(out))
        subprocess.run(['ffmpeg', '-v', 'error', '-i', tif, '-f', 'rawvideo',
                        '-pix_fmt', pix_fmt, '-y', out], check=True)
    return np.fromfile(out, dtype=dtype).reshape(shape)


def boxblur2d(a, r):
    """经度环绕、纬度边缘延拓的盒式模糊（累积和实现）"""
    H, W = a.shape
    pad = np.empty((H + 2 * r, W + 2 * r), dtype=np.float64)
    pad[r:r + H, r:r + W] = a
    pad[:r, r:r + W] = a[0]
    pad[H + r:, r:r + W] = a[-1]
    pad[:, :r] = pad[:, W:W + r]
    pad[:, W + r:] = pad[:, r:2 * r]
    pad[:r, :r] = pad[:r, W:W + r]
    pad[:r, W + r:] = pad[:r, r:2 * r]
    pad[H + r:, :r] = pad[H + r:, W:W + r]
    pad[H + r:, W + r:] = pad[H + r:, r:2 * r]
    c = np.pad(np.cumsum(np.cumsum(pad, axis=0), axis=1), ((1, 0), (1, 0)))
    n = 2 * r + 1
    return (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]) / (n * n)


def pack_rg8(v01):
    """0..1 浮点 → RG8（高字节在前），返回 uint8 一维数组"""
    q = np.clip(np.rint(v01 * 65535.0), 0, 65535).astype(np.uint16)
    out = np.empty(q.size * 2, dtype=np.uint8)
    out[0::2] = (q >> 8).astype(np.uint8).ravel()
    out[1::2] = (q & 255).astype(np.uint8).ravel()
    return out


# ── 1. 高程 ──
htif = fetch(SRC_H, os.path.join(CACHE, 'ldem_16_uint.tif'))
h = to_raw(htif, 'gray16le', os.path.join(CACHE, 'ldem.raw'), (2880, 5760), '<u2')
km = (R_DATUM_M - h.astype(np.float64) * 0.5 - R_MEAN_M) / 1000.0
hmin, hmax = float(km.min()), float(km.max())
print('· 高程 %d×%d  起伏 %.2f ~ %.2f km  均值 %.2f km' % (h.shape[1], h.shape[0], hmin, hmax, km.mean()))
h01 = (km - hmin) / (hmax - hmin)
open(os.path.join(OUT, 'moon_h.bin'), 'wb').write(pack_rg8(h01).tobytes())

# ── 2. 反照率（转为线性反射率 → 缩放到本项目亮度标定） ──
atif = fetch(SRC_A, os.path.join(CACHE, 'lroc_8k.tif'))
alb = to_raw(atif, 'rgb24', os.path.join(CACHE, 'lroc.raw'), (4096, 8192, 3), np.uint8)
alb = alb.reshape(2048, 2, 4096, 2, 3).mean(axis=(1, 3))          # 降采样到 4096×2048
lin = np.power(alb / 255.0, 2.2).mean(axis=2)                     # sRGB → 线性
lin *= 0.95                                                       # 标定：与视频/程序化模式的亮度对齐
print('· 反照率 %d×%d  反照率 %.3f ~ %.3f（中位 %.3f）' % (alb.shape[1], alb.shape[0], lin.min(), lin.max(), np.median(lin)))

# ── 3. 烘焙环境光遮蔽（坑底压暗、坑唇提亮） ──
hk = km[::2, ::2][:2048, :4096] if km.shape == (2880, 5760) else km
if hk.shape != (2048, 4096):
    yi = (np.arange(2048) * hk.shape[0] // 2048)
    xi = (np.arange(4096) * hk.shape[1] // 4096)
    hk = hk[np.ix_(yi, xi)]
blur = boxblur2d(hk, 10)
ao = np.clip(0.5 + (hk - blur) / 2.0, 0, 1)                       # ±1 km 映射到 0..1
lin *= 0.925 + 0.085 * ao
print('· AO 已烘焙')

open(os.path.join(OUT, 'moon_a.bin'), 'wb').write(pack_rg8(lin).tobytes())

# ── 4. 元数据 ──
meta = {
    'hMin': round(hmin, 3), 'hMax': round(hmax, 3),
    'w': 5760, 'h': 2880, 'aw': 4096, 'ah': 2048,
    'src': 'LRO LOLA + LROC WAC (NASA SVS CGI Moon Kit)',
}
json.dump(meta, open(os.path.join(OUT, 'meta.json'), 'w'), ensure_ascii=False, indent=1)
print('\n完成 →', os.path.abspath(OUT))
for f in ('moon_h.bin', 'moon_a.bin', 'meta.json'):
    print('  %-12s %8.1f MB' % (f, os.path.getsize(os.path.join(OUT, f)) / 1e6))
if not a.keep_cache:
    for f in ('ldem.raw', 'lroc.raw'):
        p = os.path.join(CACHE, f)
        if os.path.exists(p):
            os.remove(p)
    print('  （已清理中间 .raw 缓存，TIFF 保留在 _dev/cache/）')
