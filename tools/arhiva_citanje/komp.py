import pypdfium2 as P, sys, os
from PIL import Image
def komp(pdf_path, out, dpi=130):
    pdf = P.PdfDocument(pdf_path); im = pdf[0].render(scale=dpi / 72).to_pil(); n=len(pdf); pdf.close()
    W, H = im.size
    if W < H:  # uspravno (A4 strane): strana 1 i strana 2 (tabela 11.5) jedna pored druge
        pdf = P.PdfDocument(pdf_path); ps = [pdf[i].render(scale=dpi / 72).to_pil() for i in range(min(2, len(pdf)))]; pdf.close()
        for p_ in ps: p_.thumbnail((900, 1270))
        c = Image.new("RGB", (sum(p_.width for p_ in ps) + 20 * (len(ps) - 1), max(p_.height for p_ in ps)), "white"); x = 0
        for p_ in ps: c.paste(p_, (x, 0)); x += p_.width + 20
        c.convert("L").save(out, quality=72); return "uspravno"
    A = im.crop((0, int(H*.13), int(W*.50), int(H*.40)))      # tačke 1–4
    B = im.crop((0, int(H*.66), int(W*.50), int(H*.86)))      # 11.1–11.4
    y0, y1 = int(H*.085), int(H*.72)
    a = im.crop((int(W*.505), y0, int(W*.565), y1)); b = im.crop((int(W*.86), y0, int(W*.985), y1))
    lw = max(A.width, B.width); rh = max(a.height, b.height)
    c = Image.new("RGB", (lw + 30 + a.width + b.width + 20, max(A.height + B.height + 20, rh)), "white")
    c.paste(A, (0, 0)); c.paste(B, (0, A.height + 20)); c.paste(a, (lw + 30, 0)); c.paste(b, (lw + 30 + a.width + 20, 0))
    c.convert("L").save(out, quality=70); return "polozeno"
if __name__ == "__main__":
    print(komp(sys.argv[1], sys.argv[2]))

def komp20(pdf_path, out, dpi=130):
    pdf = P.PdfDocument(pdf_path); n = len(pdf)
    p1 = pdf[0].render(scale=dpi / 72).to_pil(); p2 = pdf[1].render(scale=dpi / 72).to_pil() if n > 1 else None
    W, H = p1.size
    if n >= 3 and W > H:  # višejezični obrazac (Vojvodina i dr.): tačka 12 je u sredini, zavisno od broja jezika
        idx = {3: [0, 1, 2], 4: [1, 2], 5: [2, 3], 6: [2, 3, 4], 7: [3, 4]}.get(n, [3, 4, 5])
        ims = [pdf[i].render(scale=dpi / 72).to_pil() for i in idx if i < n]; pdf.close()
        c = Image.new("RGB", (max(i.width for i in ims), sum(i.height for i in ims) + 20 * len(ims)), "white"); y = 0
        for im in ims: c.paste(im, (0, y)); y += im.height + 20
        c.convert("L").save(out, quality=72); return "visejezicno"
    pdf.close()
    if W < H or p2 is None:
        p1.thumbnail((1100, 1500)); p1.convert("L").save(out, quality=70); return "uspravno"
    A = p1.crop((0, int(H*.10), int(W*.50), int(H*.20)))          # broj BM i opština
    B = p1.crop((int(W*.52), int(H*.64), W, int(H*.99)))           # 12. rezultati: 12.1–12.7
    W2, H2 = p2.size; y0, y1 = int(H2*.04), int(H2*.78)
    a = p2.crop((int(W2*.02), y0, int(W2*.08), y1)); b = p2.crop((int(W2*.39), y0, int(W2*.495), y1))
    lw = max(A.width, B.width); rh = max(a.height, b.height)
    c = Image.new("RGB", (lw + 30 + a.width + b.width + 20, max(A.height + B.height + 20, rh)), "white")
    c.paste(A, (0, 0)); c.paste(B, (0, A.height + 20)); c.paste(a, (lw + 30, 0)); c.paste(b, (lw + 30 + a.width + 20, 0))
    c.convert("L").save(out, quality=70); return "polozeno"
