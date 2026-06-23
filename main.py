"""
Analisador de Plântulas de Alface
Computação Gráfica - UNISC
Prof. Rafael Peiter

Objetivo: Medir digitalmente o comprimento das estruturas de plântulas
de alface a partir de imagens, utilizando OpenCV.

Uso:
    python main.py <caminho_da_imagem>

Controles:
    - Clique esquerdo: adicionar ponto ao longo da raiz
    - Z: desfazer último ponto
    - ENTER / N: finalizar medição da plântula atual e passar para próxima
    - R: resetar medição da plântula atual
    - S: salvar resultados e imagem anotada
    - Q / ESC: sair do programa
    - +/-: zoom in/out
    - Arrastar com botão direito: mover imagem (pan)

Fluxo de medição por plântula:
    Fase 1: Clique do TOPO da estrutura branca até o ponto de ESTRANGULAMENTO
            (seguindo o caminho real do filamento)
    Fase 2: Clique do ponto de ESTRANGULAMENTO até a EXTREMIDADE FINAL da raiz
            (seguindo curvas e enrolamentos)
    ENTER: confirma a plântula e inicia a próxima
"""

import cv2
import numpy as np
import sys
import os
import json
import math
from datetime import datetime
from PIL import Image
import pillow_heif

#Registra o suporte a arquivos HEIC/HEIF do iPhone
pillow_heif.register_heif_opener()

#Configurações visuais 
COR_SEGMENTO1  = (0, 200, 0)      #Verde – do topo ao estrangulamento
COR_SEGMENTO2  = (255, 80, 0)     #Laranja – do estrangulamento à extremidade
COR_TOTAL      = (0, 0, 255)      #Vermelho – linha total (apenas HUD)
COR_PONTO      = (255, 255, 0)    #Amarelo – pontos clicados
COR_ESTRANG    = (255, 0, 255)    #Magenta – ponto de estrangulamento
COR_TOPO       = (0, 255, 255)    #Ciano – topo
COR_EXTREMIDADE= (0, 100, 255)    #Laranja-escuro – extremidade final
RAIO_PONTO     = 8
ESPESSURA_LINHA= 3

#Estado global
class Estado:
    def __init__(self, img_path):
        #Suporte a carregamento de imagens nativas do iOS (.HEIC)
        if img_path.lower().endswith(('.heic', '.heif')):
            try:
                img_pil = Image.open(img_path)
                self.img_original = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            except Exception as e:
                raise FileNotFoundError(f"Não foi possível converter o arquivo HEIC: {img_path}. Erro: {e}")
        else:
            self.img_original = cv2.imread(img_path)
            
        if self.img_original is None:
            raise FileNotFoundError(f"Não foi possível abrir: {img_path}")

        self.img_path   = img_path
        self.img_nome   = os.path.basename(img_path)
        self.h_orig, self.w_orig = self.img_original.shape[:2]

        #Calibração (px → mm)
        self.mm_por_px  = None          #definido após calibração
        self.cal_pts    = []            #pontos usados para calibrar
        self.cal_mm     = 0.0
        self.calibrado  = False

        #Plântulas medidas
        self.plantulas  = []            #lista de dicts com resultados

        #Plântula em andamento
        self.numero_atual     = 1
        self.fase             = 1       #1 = seg1, 2 = seg2
        self.pontos_seg1      = []      #[(x, y), ...]
        self.pontos_seg2      = []

        #Visualização
        self.zoom         = 1.0
        self.offset_x     = 0
        self.offset_y     = 0
        self.pan_inicio   = None
        self.pan_offset_inicio = None

        #Janela
        self.win_w        = 1280
        self.win_h        = 800
        self.modo         = "calibracao"   #"calibracao" | "medicao"

    #Utilidades de coordenadas
    def tela_para_img(self, tx, ty):
        ix = int((tx - self.offset_x) / self.zoom)
        iy = int((ty - self.offset_y) / self.zoom)
        return ix, iy

    def img_para_tela(self, ix, iy):
        tx = int(ix * self.zoom + self.offset_x)
        ty = int(iy * self.zoom + self.offset_y)
        return tx, ty

    #Comprimento de polilinha
    def comprimento_px(self, pontos):
        total = 0.0
        for i in range(1, len(pontos)):
            dx = pontos[i][0] - pontos[i-1][0]
            dy = pontos[i][1] - pontos[i-1][1]
            total += math.sqrt(dx*dx + dy*dy)
        return total

    def px_para_mm(self, px):
        if self.mm_por_px is None:
            return None
        return px * self.mm_por_px

    #Finalizar plântula atual
    def finalizar_plantula(self):
        if len(self.pontos_seg1) < 2:
            return False

        seg1_px = self.comprimento_px(self.pontos_seg1)
        seg2_px = self.comprimento_px(self.pontos_seg2) if len(self.pontos_seg2) >= 2 else 0.0
        total_px = seg1_px + seg2_px

        seg1_mm  = self.px_para_mm(seg1_px)
        seg2_mm  = self.px_para_mm(seg2_px)
        total_mm = self.px_para_mm(total_px)

        self.plantulas.append({
            "numero"       : self.numero_atual,
            "pontos_seg1"  : list(self.pontos_seg1),
            "pontos_seg2"  : list(self.pontos_seg2),
            "seg1_px"      : seg1_px,
            "seg2_px"      : seg2_px,
            "total_px"     : total_px,
            "seg1_mm"      : seg1_mm,
            "seg2_mm"      : seg2_mm,
            "total_mm"     : total_mm,
        })

        self.numero_atual += 1
        self.fase          = 1
        self.pontos_seg1   = []
        self.pontos_seg2   = []
        return True

    #Desfazer
    def desfazer(self):
        if self.fase == 2 and self.pontos_seg2:
            self.pontos_seg2.pop()
            if not self.pontos_seg2:
                self.fase = 2   #mantém fase 2, pode clicar novamente
        elif self.fase == 2 and not self.pontos_seg2:
            self.fase = 1
        elif self.fase == 1 and self.pontos_seg1:
            self.pontos_seg1.pop()

    #Reset plântula 
    def resetar(self):
        self.fase        = 1
        self.pontos_seg1 = []
        self.pontos_seg2 = []


#Desenho
def desenhar_frame(estado: Estado):
    """Compõe o frame completo para exibição."""
    #Imagem com zoom e pan
    h_vis = int(estado.h_orig * estado.zoom)
    w_vis = int(estado.w_orig * estado.zoom)
    img_vis = cv2.resize(estado.img_original, (w_vis, h_vis), interpolation=cv2.INTER_LINEAR)

    #Canvas (fundo preto)
    canvas = np.zeros((estado.win_h, estado.win_w, 3), dtype=np.uint8)
    canvas[:] = (40, 40, 40)

    #Região visível
    ox, oy = estado.offset_x, estado.offset_y
    x1_src = max(0, -ox);          y1_src = max(0, -oy)
    x2_src = min(w_vis, estado.win_w - ox)
    y2_src = min(h_vis, estado.win_h - oy)
    x1_dst = max(0, ox);           y1_dst = max(0, oy)
    x2_dst = x1_dst + (x2_src - x1_src)
    y2_dst = y1_dst + (y2_src - y1_src)

    if x2_src > x1_src and y2_src > y1_src:
        canvas[y1_dst:y2_dst, x1_dst:x2_dst] = img_vis[y1_src:y2_src, x1_src:x2_src]

    #Desenhar plântulas já finalizadas
    for p in estado.plantulas:
        _desenhar_segmento(canvas, estado, p["pontos_seg1"], COR_SEGMENTO1)
        _desenhar_segmento(canvas, estado, p["pontos_seg2"], COR_SEGMENTO2)
        #Label do número
        if p["pontos_seg1"]:
            tx, ty = estado.img_para_tela(*p["pontos_seg1"][0])
            cv2.putText(canvas, f"P{p['numero']}", (tx+6, ty-6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

    #Desenhar plântula atual
    _desenhar_segmento(canvas, estado, estado.pontos_seg1, COR_SEGMENTO1)
    _desenhar_segmento(canvas, estado, estado.pontos_seg2, COR_SEGMENTO2)

    #Pontos especiais da plântula atual
    if estado.pontos_seg1:
        tx, ty = estado.img_para_tela(*estado.pontos_seg1[0])
        cv2.circle(canvas, (tx, ty), RAIO_PONTO+2, COR_TOPO, -1)
        cv2.putText(canvas, "TOPO", (tx+8, ty-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COR_TOPO, 2)

    if estado.pontos_seg1 and estado.fase == 2:
        tx, ty = estado.img_para_tela(*estado.pontos_seg1[-1])
        cv2.circle(canvas, (tx, ty), RAIO_PONTO+2, COR_ESTRANG, -1)
        cv2.putText(canvas, "ESTRANG.", (tx+8, ty-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COR_ESTRANG, 2)

    if estado.pontos_seg2:
        tx, ty = estado.img_para_tela(*estado.pontos_seg2[-1])
        cv2.circle(canvas, (tx, ty), RAIO_PONTO+2, COR_EXTREMIDADE, -1)

    #Pontos de calibraçã
    if estado.modo == "calibracao":
        for i, pt in enumerate(estado.cal_pts):
            tx, ty = estado.img_para_tela(*pt)
            cv2.circle(canvas, (tx, ty), RAIO_PONTO, (0, 255, 255), -1)
            label = "A" if i == 0 else "B"
            cv2.putText(canvas, label, (tx+8, ty-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        if len(estado.cal_pts) == 2:
            tA = estado.img_para_tela(*estado.cal_pts[0])
            tB = estado.img_para_tela(*estado.cal_pts[1])
            cv2.line(canvas, tA, tB, (0, 255, 255), 2, cv2.LINE_AA)

    #HU
    _desenhar_hud(canvas, estado)

    return canvas


def _desenhar_segmento(canvas, estado, pontos, cor):
    if len(pontos) < 2:
        #Só o ponto inicial
        if pontos:
            tx, ty = estado.img_para_tela(*pontos[0])
            cv2.circle(canvas, (tx, ty), RAIO_PONTO, cor, -1)
        return
    pts_tela = [estado.img_para_tela(*p) for p in pontos]
    for i in range(1, len(pts_tela)):
        cv2.line(canvas, pts_tela[i-1], pts_tela[i], cor, ESPESSURA_LINHA, cv2.LINE_AA)
    for pt in pts_tela:
        cv2.circle(canvas, pt, RAIO_PONTO, cor, -1)


def _desenhar_hud(canvas, estado: Estado):
    """Painel de informações no canto superior esquerdo."""
    hud_h, hud_w = canvas.shape[:2]

    #Fundo semitransparente
    overlay = canvas.copy()
    cv2.rectangle(overlay, (0, 0), (420, 260), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.75, canvas, 0.25, 0, canvas)

    y = 22
    def linha(txt, cor=(220,220,220), escala=0.55, esp=2):
        nonlocal y
        cv2.putText(canvas, txt, (10, y), cv2.FONT_HERSHEY_SIMPLEX, escala, cor, esp)
        y += 22

    if estado.modo == "calibracao":
        linha("=== CALIBRAÇÃO ===", (0, 220, 255), 0.65, 2)
        linha("Clique em 2 pontos conhecidos da régua", (200,200,200))
        linha(f"Pontos selecionados: {len(estado.cal_pts)}/2")
        if len(estado.cal_pts) == 2:
            dx = estado.cal_pts[1][0] - estado.cal_pts[0][0]
            dy = estado.cal_pts[1][1] - estado.cal_pts[0][1]
            dist_px = math.sqrt(dx*dx + dy*dy)
            linha(f"Distância: {dist_px:.1f} px")
            linha("Digite o valor real (mm) no terminal")
        linha("Z: desfazer ponto | ENTER: confirmar", (180,180,180))
    else:
        linha("=== MEDIÇÃO ===", (0, 220, 100), 0.65, 2)
        fase_txt = "Fase 1: Topo → Estrangulamento" if estado.fase == 1 \
                   else "Fase 2: Estrangulamento → Extremidade"
        cor_fase = COR_SEGMENTO1 if estado.fase == 1 else COR_SEGMENTO2
        linha(fase_txt, cor_fase, 0.55, 2)
        linha(f"Plântula atual: #{estado.numero_atual}")

        seg1_px = estado.comprimento_px(estado.pontos_seg1)
        seg2_px = estado.comprimento_px(estado.pontos_seg2)
        total_px = seg1_px + seg2_px

        if estado.calibrado:
            s1mm  = estado.px_para_mm(seg1_px)
            s2mm  = estado.px_para_mm(seg2_px)
            totmm = estado.px_para_mm(total_px)
            linha(f"Seg1 (verde):   {seg1_px:.0f}px = {s1mm:.2f}mm", COR_SEGMENTO1)
            linha(f"Seg2 (laranja): {seg2_px:.0f}px = {s2mm:.2f}mm", COR_SEGMENTO2)
            linha(f"Total:          {total_px:.0f}px = {totmm:.2f}mm", COR_TOTAL)
        else:
            linha(f"Seg1 (verde):   {seg1_px:.0f}px", COR_SEGMENTO1)
            linha(f"Seg2 (laranja): {seg2_px:.0f}px", COR_SEGMENTO2)
            linha(f"Total:          {total_px:.0f}px", COR_TOTAL)
        linha("")
        linha(f"Plântulas salvas: {len(estado.plantulas)}")
        linha("ENTER=próxima | Z=desfazer | R=reset", (180,180,180))
        linha("S=salvar | +=zoom+ | -=zoom- | Q=sair", (180,180,180))

    #Calibração info (canto inferior esquerdo)
    if estado.calibrado:
        txt = f"Calibração: {estado.mm_por_px*1000:.4f} mm/px  ({estado.cal_mm:.1f}mm ref)"
        cv2.putText(canvas, txt, (10, hud_h-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,220,100), 1)
    else:
        cv2.putText(canvas, "Sem calibração", (10, hud_h-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80,80,200), 1)

    # Zoom
    cv2.putText(canvas, f"Zoom: {estado.zoom:.1f}x", (hud_w-120, hud_h-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)


#Callbacks do mouse 
def mouse_callback(event, x, y, flags, estado: Estado):
    if event == cv2.EVENT_MOUSEWHEEL:
        fator = 1.12 if flags > 0 else 1/1.12
        _aplicar_zoom(estado, fator, x, y)
        return

    if event == cv2.EVENT_RBUTTONDOWN:
        estado.pan_inicio         = (x, y)
        estado.pan_offset_inicio  = (estado.offset_x, estado.offset_y)
        return

    if event == cv2.EVENT_MOUSEMOVE and flags & cv2.EVENT_FLAG_RBUTTON:
        if estado.pan_inicio:
            dx = x - estado.pan_inicio[0]
            dy = y - estado.pan_inicio[1]
            estado.offset_x = estado.pan_offset_inicio[0] + dx
            estado.offset_y = estado.pan_offset_inicio[1] + dy
        return

    if event == cv2.EVENT_RBUTTONUP:
        estado.pan_inicio = None
        return

    if event == cv2.EVENT_LBUTTONDOWN:
        ix, iy = estado.tela_para_img(x, y)
        #Garantir dentro da imagem
        ix = max(0, min(ix, estado.w_orig-1))
        iy = max(0, min(iy, estado.h_orig-1))

        if estado.modo == "calibracao":
            if len(estado.cal_pts) < 2:
                estado.cal_pts.append((ix, iy))
            return

        #Modo medição
        if estado.fase == 1:
            estado.pontos_seg1.append((ix, iy))
        else:
            #Primeiro ponto do seg2 = último ponto do seg1 (automático na transição)
            estado.pontos_seg2.append((ix, iy))


def _aplicar_zoom(estado, fator, cx, cy):
    novo_zoom = max(0.2, min(estado.zoom * fator, 10.0))
    #Zoom centrado no cursor
    estado.offset_x = int(cx - (cx - estado.offset_x) * (novo_zoom / estado.zoom))
    estado.offset_y = int(cy - (cy - estado.offset_y) * (novo_zoom / estado.zoom))
    estado.zoom = novo_zoom


#Salvar resultados
def salvar_resultados(estado: Estado):
    if not estado.plantulas:
        print("[AVISO] Nenhuma plântula para salvar.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base      = os.path.splitext(estado.img_nome)[0]
    dir_out   = os.path.dirname(estado.img_path) or "."

    #Imagem anotada
    img_out = estado.img_original.copy()
    for p in estado.plantulas:
        #Segmentos
        for i in range(1, len(p["pontos_seg1"])):
            cv2.line(img_out, p["pontos_seg1"][i-1], p["pontos_seg1"][i],
                     COR_SEGMENTO1, 4, cv2.LINE_AA)
        for i in range(1, len(p["pontos_seg2"])):
            cv2.line(img_out, p["pontos_seg2"][i-1], p["pontos_seg2"][i],
                     COR_SEGMENTO2, 4, cv2.LINE_AA)
        #Pontos
        for pt in p["pontos_seg1"]:
            cv2.circle(img_out, pt, 10, COR_SEGMENTO1, -1)
        for pt in p["pontos_seg2"]:
            cv2.circle(img_out, pt, 10, COR_SEGMENTO2, -1)
        #Marcadores especiais
        if p["pontos_seg1"]:
            cv2.circle(img_out, p["pontos_seg1"][0],  14, COR_TOPO,    3)
            cv2.circle(img_out, p["pontos_seg1"][-1], 14, COR_ESTRANG, 3)
        if p["pontos_seg2"]:
            cv2.circle(img_out, p["pontos_seg2"][-1], 14, COR_EXTREMIDADE, 3)
        # Label
        if p["pontos_seg1"]:
            cv2.putText(img_out, f"P{p['numero']}", 
                        (p["pontos_seg1"][0][0]+12, p["pontos_seg1"][0][1]-12),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,255), 3)

    img_path_out = os.path.join(dir_out, f"{base}_anotado_{timestamp}.png")
    cv2.imwrite(img_path_out, img_out)
    print(f"[OK] Imagem anotada salva: {img_path_out}")

    #Relatório texto
    txt_path = os.path.join(dir_out, f"{base}_resultados_{timestamp}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("RELATÓRIO - ANÁLISE DE PLÂNTULAS DE ALFACE\n")
        f.write(f"Imagem: {estado.img_nome}\n")
        f.write(f"Data/hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        if estado.calibrado:
            f.write(f"Calibração: {estado.mm_por_px*1000:.5f} mm/px "
                    f"(referência: {estado.cal_mm:.1f}mm)\n")
        else:
            f.write("Calibração: não realizada (medidas apenas em pixels)\n")
        f.write("=" * 60 + "\n\n")

        #Cabeçalho da tabela
        if estado.calibrado:
            f.write(f"{'Plântula':<10} {'Seg1 (px)':<12} {'Seg1 (mm)':<12} "
                    f"{'Seg2 (px)':<12} {'Seg2 (mm)':<12} "
                    f"{'Total (px)':<12} {'Total (mm)':<12}\n")
            f.write("-" * 84 + "\n")
        else:
            f.write(f"{'Plântula':<10} {'Seg1 (px)':<12} {'Seg2 (px)':<12} {'Total (px)':<12}\n")
            f.write("-" * 48 + "\n")

        for p in estado.plantulas:
            if estado.calibrado:
                f.write(f"{'P'+str(p['numero']):<10} "
                        f"{p['seg1_px']:<12.1f} {p['seg1_mm']:<12.2f} "
                        f"{p['seg2_px']:<12.1f} {p['seg2_mm']:<12.2f} "
                        f"{p['total_px']:<12.1f} {p['total_mm']:<12.2f}\n")
            else:
                f.write(f"{'P'+str(p['numero']):<10} "
                        f"{p['seg1_px']:<12.1f} {p['seg2_px']:<12.1f} "
                        f"{p['total_px']:<12.1f}\n")

        #Estatísticas
        f.write("\n" + "=" * 60 + "\n")
        f.write("ESTATÍSTICAS\n")
        f.write("-" * 60 + "\n")
        totais_px = [p["total_px"] for p in estado.plantulas]
        f.write(f"Nº de plântulas medidas: {len(estado.plantulas)}\n")
        f.write(f"Total médio (px): {np.mean(totais_px):.1f}\n")
        if estado.calibrado:
            totais_mm = [p["total_mm"] for p in estado.plantulas]
            f.write(f"Total médio (mm): {np.mean(totais_mm):.2f}\n")
            f.write(f"Total mínimo (mm): {min(totais_mm):.2f}\n")
            f.write(f"Total máximo (mm): {max(totais_mm):.2f}\n")

    print(f"[OK] Relatório salvo: {txt_path}")

    #JSON com dados completo
    json_path = os.path.join(dir_out, f"{base}_dados_{timestamp}.json")
    dados = {
        "imagem"      : estado.img_nome,
        "timestamp"   : timestamp,
        "calibracao"  : {
            "realizada"   : estado.calibrado,
            "mm_por_px"   : estado.mm_por_px,
            "referencia_mm": estado.cal_mm,
        },
        "plantulas"   : estado.plantulas,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    print(f"[OK] Dados JSON salvos: {json_path}")

    return img_path_out, txt_path


#Loop principal
def main():
    if len(sys.argv) < 2:
        print("Uso: python plantula_analyzer.py <caminho_da_imagem>")
        print("\nExemplo:")
        print("  python plantula_analyzer.py IMG_3196.png")
        sys.exit(1)

    argumento_img = sys.argv[1]
    
    #Adiciona o prefixo 'Img/' caso o usuário digite apenas o nome da imagem
    if not argumento_img.startswith("Img/") and not os.path.isabs(argumento_img):
        img_path = os.path.join("Img", argumento_img)
    else:
        img_path = argumento_img

    print(f"\n{'='*60}")
    print("  ANALISADOR DE PLÂNTULAS DE ALFACE — UNISC")
    print(f"{'='*60}")
    print(f"Imagem configurada: {img_path}")

    try:
        estado = Estado(img_path)
    except FileNotFoundError as e:
        print(f"[ERRO] {e}")
        sys.exit(1)

    print(f"Tamanho: {estado.w_orig} x {estado.h_orig} px")

    #Ajuste de zoom inicial para caber na tela
    zoom_fit_w = estado.win_w / estado.w_orig
    zoom_fit_h = estado.win_h / estado.h_orig
    estado.zoom = min(zoom_fit_w, zoom_fit_h) * 0.95

    #Centralizar
    estado.offset_x = int((estado.win_w - estado.w_orig * estado.zoom) / 2)
    estado.offset_y = int((estado.win_h - estado.h_orig * estado.zoom) / 2)

    #Janela
    cv2.namedWindow("Analisador de Plântulas", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Analisador de Plântulas", estado.win_w, estado.win_h)
    cv2.setMouseCallback("Analisador de Plântulas",
                         lambda e,x,y,f,p: mouse_callback(e,x,y,f,estado))

    print("\n[CALIBRAÇÃO]")
    print("  1. Clique em dois pontos na régua que você conhece a distância.")
    print("  2. Pressione ENTER para confirmar e informar a distância em mm.")
    print("  3. Pressione Z para desfazer o último ponto.")
    print("  4. Pressione ESC para pular a calibração (medidas em px).\n")

    while True:
        frame = desenhar_frame(estado)
        cv2.imshow("Analisador de Plântulas", frame)
        key = cv2.waitKey(20) & 0xFF

        #Teclas 
        if key in (ord('q'), 27) and estado.modo == "medicao":
            break

        if key == 27 and estado.modo == "calibracao":
            #Pular calibração
            print("[INFO] Calibração ignorada. Medidas serão em pixels.")
            estado.modo = "medicao"
            print("\n[MEDIÇÃO INICIADA]")
            _imprimir_instrucoes_medicao()

        if key == ord('z') or key == ord('Z'):
            if estado.modo == "calibracao":
                if estado.cal_pts:
                    estado.cal_pts.pop()
            else:
                estado.desfazer()

        if key == ord('r') or key == ord('R'):
            if estado.modo == "medicao":
                estado.resetar()
                print(f"[RESET] Plântula #{estado.numero_atual} resetada.")

        if key == 13 or key == 10:   #ENTER (\r ou \n)
            if estado.modo == "calibracao":
                if len(estado.cal_pts) == 2:
                    dx = estado.cal_pts[1][0] - estado.cal_pts[0][0]
                    dy = estado.cal_pts[1][1] - estado.cal_pts[0][1]
                    dist_px = math.sqrt(dx*dx + dy*dy)
                    try:
                        mm_input = input(f"\nDistância entre os dois pontos em mm "
                                         f"(distância em px: {dist_px:.1f}): ")
                        mm_val = float(mm_input.replace(",", "."))
                        if mm_val <= 0:
                            raise ValueError
                        estado.mm_por_px  = mm_val / dist_px
                        estado.cal_mm     = mm_val
                        estado.calibrado  = True
                        print(f"[OK] Calibração: {dist_px:.1f}px = {mm_val}mm "
                              f"→ {estado.mm_por_px*1000:.4f} mm/px")
                        estado.modo = "medicao"
                        print("\n[MEDIÇÃO INICIADA]")
                        _imprimir_instrucoes_medicao()
                    except (ValueError, EOFError):
                        print("[AVISO] Valor inválido, calibração ignorada.")
                        estado.modo = "medicao"
                        _imprimir_instrucoes_medicao()
                else:
                    print(f"[AVISO] Selecione 2 pontos antes de confirmar "
                          f"(selecionados: {len(estado.cal_pts)}).")

            elif estado.modo == "medicao":
                if estado.fase == 1:
                    if len(estado.pontos_seg1) >= 2:
                        print(f"[INFO] Fase 1 concluída com {len(estado.pontos_seg1)} pontos.")
                        print("  Agora clique do estrangulamento até a extremidade da raiz.")
                        print("  O primeiro ponto do segmento 2 já foi definido.")
                        #Copiar último ponto do seg1 como início do seg2
                        estado.pontos_seg2 = [estado.pontos_seg1[-1]]
                        estado.fase = 2
                    else:
                        print("[AVISO] Clique ao menos 2 pontos no Segmento 1.")
                else:  #fase 2: finalizar
                    ok = estado.finalizar_plantula()
                    if ok:
                        p = estado.plantulas[-1]
                        print(f"\n[PLÂNTULA #{p['numero']} SALVA]")
                        print(f"  Seg1: {p['seg1_px']:.1f}px", end="")
                        if p['seg1_mm']: print(f" = {p['seg1_mm']:.2f}mm", end="")
                        print()
                        print(f"  Seg2: {p['seg2_px']:.1f}px", end="")
                        if p['seg2_mm']: print(f" = {p['seg2_mm']:.2f}mm", end="")
                        print()
                        print(f"  Total: {p['total_px']:.1f}px", end="")
                        if p['total_mm']: print(f" = {p['total_mm']:.2f}mm", end="")
                        print()
                        print(f"\n[INFO] Iniciando plântula #{estado.numero_atual}...")
                    else:
                        print("[AVISO] Clique ao menos 2 pontos no Segmento 1.")

        if key in (ord('+'), ord('=')):
            _aplicar_zoom(estado, 1.2, estado.win_w//2, estado.win_h//2)

        if key in (ord('-'), ord('_')):
            _aplicar_zoom(estado, 1/1.2, estado.win_w//2, estado.win_h//2)

        if key == ord('s') or key == ord('S'):
            if estado.modo == "medicao":
                salvar_resultados(estado)

    #Salvar ao sair se houver dados
    if estado.plantulas:
        resp = input("\nSalvar resultados antes de sair? [S/n]: ").strip().lower()
        if resp != 'n':
            salvar_resultados(estado)

    cv2.destroyAllWindows()
    print("\nPrograma encerrado.")


def _imprimir_instrucoes_medicao():
    print("\n  Fase 1 – Clique do TOPO da estrutura branca até o ponto de ESTRANGULAMENTO")
    print("           (seguindo o formato real do filamento)")
    print("  ENTER  → confirma Fase 1 e inicia Fase 2")
    print("\n  Fase 2 – Clique do ESTRANGULAMENTO até a EXTREMIDADE FINAL da raiz")
    print("           (incluindo curvas e partes enroladas)")
    print("  ENTER  → salva a plântula e inicia a próxima")
    print("\n  Z=desfazer | R=resetar plântula atual | S=salvar | Q=sair\n")


if __name__ == "__main__":
    main()