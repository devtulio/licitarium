# Gera design/splash.png — a imagem que o PyInstaller mostra enquanto extrai a
# runtime do exe (antes de qualquer código Python rodar). É a composição
# "cartão com selo" do tema Portal, o padrão do aplicativo.
from PIL import Image, ImageDraw, ImageFont

L, A = 460, 240                      # tamanho final da janelinha de splash
F = 4                                # supersample para bordas suaves

FUNDO = (248, 249, 250, 255)         # --bg do tema Portal
CARTAO = (255, 255, 255, 255)
BORDA = (227, 230, 232, 255)
TEXTO = (27, 27, 27, 255)
SUAVE = (92, 102, 112, 255)
ACENTO = (19, 81, 180, 255)
RED = (139, 46, 46, 255)             # selo
CREAM = (245, 239, 226, 255)

GEORGIA = "C:/Windows/Fonts/georgia.ttf"
SEGOE = "C:/Windows/Fonts/segoeui.ttf"


def _fonte(caminho, tamanho, alt=GEORGIA):
    try:
        return ImageFont.truetype(caminho, tamanho)
    except OSError:
        return ImageFont.truetype(alt, tamanho)


def _selo(d, x, y, lado):
    """Tabula ansata (design/icone-t1.svg) na escala pedida."""
    e = lado / 64.0                  # o SVG original é 64x64
    px = lambda vx, vy: (x + vx * e, y + vy * e)
    d.polygon([px(11, 25), px(3, 19), px(3, 45), px(11, 39)], fill=RED)
    d.polygon([px(53, 25), px(61, 19), px(61, 45), px(53, 39)], fill=RED)
    d.rectangle([px(9, 17), px(55, 47)], fill=RED)
    d.rectangle([px(12.5, 20.5), px(51.5, 43.5)],
                outline=(245, 239, 226, 180), width=max(1, round(1.4 * e)))
    fonte = _fonte(GEORGIA, round(21 * e))
    cx, cy = px(32, 40.5)
    d.text((cx, cy), "L", font=fonte, fill=CREAM, anchor="ms")


def desenhar():
    img = Image.new("RGBA", (L * F, A * F), FUNDO)
    d = ImageDraw.Draw(img)

    # cartão central
    cw, ch = 372 * F, 116 * F
    cx0, cy0 = (L * F - cw) // 2, (A * F - ch) // 2
    d.rounded_rectangle([cx0, cy0, cx0 + cw, cy0 + ch], radius=8 * F,
                        fill=CARTAO, outline=BORDA, width=F)

    _selo(d, cx0 + 26 * F, cy0 + 26 * F, 64 * F)

    tx = cx0 + 110 * F
    d.text((tx, cy0 + 46 * F), "L I C I T A R I", font=_fonte(GEORGIA, 25 * F),
           fill=TEXTO, anchor="ls")
    largura_pre = d.textlength("L I C I T A R I ", font=_fonte(GEORGIA, 25 * F))
    d.text((tx + largura_pre, cy0 + 46 * F), "V", font=_fonte(GEORGIA, 25 * F),
           fill=ACENTO, anchor="ls")
    largura_v = d.textlength("V ", font=_fonte(GEORGIA, 25 * F))
    d.text((tx + largura_pre + largura_v, cy0 + 46 * F), "M",
           font=_fonte(GEORGIA, 25 * F), fill=TEXTO, anchor="ls")

    d.text((tx, cy0 + 66 * F), "Repositório de contratações públicas",
           font=_fonte(SEGOE, 11 * F, SEGOE), fill=SUAVE, anchor="ls")

    # trilho + trecho preenchido (a extração não reporta progresso real)
    ty = cy0 + 84 * F
    d.rounded_rectangle([tx, ty, cx0 + cw - 26 * F, ty + 3 * F],
                        radius=2 * F, fill=(233, 237, 243, 255))
    d.rounded_rectangle([tx, ty, tx + 70 * F, ty + 3 * F],
                        radius=2 * F, fill=ACENTO)

    return img.resize((L, A), Image.LANCZOS)


if __name__ == "__main__":
    img = desenhar()
    img.convert("RGB").save("splash.png")
    print("splash.png", img.size)
