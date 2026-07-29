# Gera licitarium.ico multi-frame a partir da geometria T1 (tabula ansata).
# Frames 256/128/64/48/32 usam a arte completa; 24/16 usam o frame dedicado
# (sem filete, L maior). Receita: desenhar a 1024px e reduzir com LANCZOS;
# frames ordenados do maior para o menor; fundo transparente.
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RED = (139, 46, 46, 255)      # #8b2e2e
CREAM = (245, 239, 226, 255)  # #f5efe2
CREAM70 = (245, 239, 226, 178)
F = 16                        # supersample: viewBox 64 -> canvas 1024


def _canvas():
    img = Image.new("RGBA", (64 * F, 64 * F), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _pt(*coords):
    return [(x * F, y * F) for x, y in coords]


def arte_completa():
    img, d = _canvas()
    d.polygon(_pt((11, 25), (3, 19), (3, 45), (11, 39)), fill=RED)
    d.polygon(_pt((53, 25), (61, 19), (61, 45), (53, 39)), fill=RED)
    d.rectangle([9 * F, 17 * F, 55 * F, 47 * F], fill=RED)
    d.rectangle([12.5 * F, 20.5 * F, 51.5 * F, 43.5 * F],
                outline=CREAM70, width=round(1.4 * F))
    font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 21 * F)
    d.text((32 * F, 40.5 * F), "L", font=font, fill=CREAM, anchor="ms")
    return img


def arte_16px():
    img, d = _canvas()
    d.polygon(_pt((10, 24), (1, 17), (1, 47), (10, 40)), fill=RED)
    d.polygon(_pt((54, 24), (63, 17), (63, 47), (54, 40)), fill=RED)
    d.rectangle([8 * F, 13 * F, 56 * F, 51 * F], fill=RED)
    font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 38 * F)
    # branco puro: a 16px o tom creme não sobrevive e cada nível de contraste conta
    d.text((32 * F, 47 * F), "L", font=font, fill=(255, 255, 255, 255), anchor="ms")
    return img


def main():
    completa, dedicada = arte_completa(), arte_16px()
    frames = [(s, completa) for s in (256, 128, 64, 48, 32)] + \
             [(s, dedicada) for s in (24, 16)]
    imgs = []
    for s, art in frames:
        im = art.resize((s, s), Image.LANCZOS)
        if s <= 24:  # frames pequenos: recuperar nitidez perdida na redução
            im = im.filter(ImageFilter.SHARPEN)
        imgs.append(im)
    imgs[0].save("licitarium.ico", format="ICO", append_images=imgs[1:])
    completa.resize((256, 256), Image.LANCZOS).save("icone-preview-256.png")
    dedicada.resize((16, 16), Image.LANCZOS).filter(ImageFilter.SHARPEN) \
            .resize((128, 128), Image.NEAREST) \
            .save("icone-preview-16x.png")  # 16px ampliado 8x p/ inspeção
    completa.resize((32, 32), Image.LANCZOS).resize((128, 128), Image.NEAREST) \
            .save("icone-preview-32x.png")  # 32px ampliado 4x p/ inspeção
    ico = Image.open("licitarium.ico")
    print("frames:", ico.info.get("sizes"))


if __name__ == "__main__":
    main()
