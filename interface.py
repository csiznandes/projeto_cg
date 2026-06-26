import cv2
import numpy as np
import os
import json
import math
from datetime import datetime
from estado import Estado
from config import (COR_SEGMENTO1, COR_SEGMENTO2, COR_TOTAL, COR_PONTO, 
                    COR_ESTRANG, COR_TOPO, COR_EXTREMIDADE, RAIO_PONTO, ESPESSURA_LINHA)

def desenhar_frame(estado: Estado):
    """Compõe o frame completo para exibição."""
    h_vis = int(estado.h_orig * estado.zoom)
    w_vis = int(estado.w_orig * estado.zoom)
    img_vis = cv2.resize(estado.img_original, (w_vis, h_vis), interpolation=cv2.INTER_LINEAR)

    canvas = np.zeros((estado.win_h, estado.win_w, 3), dtype=np.uint8)
    canvas[:] = (40, 40, 40)

    ox, oy = estado.offset_x, estado.offset_y
    x1_src = max(0, -ox);          y1_src = max(0, -oy)
    x2_src = min(w_vis, estado.win_w - ox)
    y2_src = min(h_vis, estado.win_h - oy)
    x1_dst = max(0, ox);           y1_dst = max(0, oy)
    x2_dst = x1_dst + (x2_src - x1_src)
    y2_dst = y1_dst + (y2_src - y1_src)

    if x2_src > x1_src and y2_src > y1_src:
        canvas[y1_dst:y2_dst, x1_dst:x2_dst] = img_vis[y1_src:y2_src, x1_src:x2_src]

    for p in estado.plantulas:
        _desenhar_segmento(canvas, estado, p["pontos_seg1"], COR_SEGMENTO1)
        _desenhar_segmento(canvas, estado, p["pontos_seg2"], COR_SEGMENTO2)
        if p["pontos_seg1"]:
            tx, ty = estado.img_para_tela(*p["pontos_seg1"][0])
            cv2.putText(canvas, f"P{p['numero']}", (tx+6, ty-6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

    _desenhar_segmento(canvas, estado, estado.pontos_seg1, COR_SEGMENTO1)
    _desenhar_segmento(canvas, estado, estado.pontos_seg2, COR_SEGMENTO2)

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

    _desenhar_hud(canvas, estado)
    return canvas

def _desenhar_segmento(canvas, estado, pontos, cor):
    if len(pontos) < 2:
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
    hud_h, hud_w = canvas.shape[:2]
    overlay = canvas.copy()
    cv2.rectangle(overlay, (0, 0), (420, 260), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.75, canvas, 0.25, 0, canvas)

    y = 22
    def linha(txt, cor=(220,220,220), escala=0.55, esp=2):
        nonlocal y
        cv2.putText(canvas, txt, (10, y), cv2.FONT_HERSHEY_SIMPLEX, escala, cor, esp)
        y += 22

    if estado.modo == "calibracao":
        linha("CALIBRACAO", (0, 220, 255), 0.65, 2)
        linha("Clique em 2 pontos conhecidos da regua", (200,200,200))
        linha(f"Pontos selecionados: {len(estado.cal_pts)}/2")
        if len(estado.cal_pts) == 2:
            dx = estado.cal_pts[1][0] - estado.cal_pts[0][0]
            dy = estado.cal_pts[1][1] - estado.cal_pts[0][1]
            dist_px = math.sqrt(dx*dx + dy*dy)
            linha(f"Distancia: {dist_px:.1f} px")
            linha("Digite o valor real (mm) no terminal")
        linha("Z: desfazer ponto | ENTER: confirmar", (180,180,180))
    else:
        linha("MEDICAO", (0, 220, 100), 0.65, 2)
        fase_txt = "Fase 1: Topo → Estrangulamento" if estado.fase == 1 else "Fase 2: Estrangulamento → Extremidade"
        cor_fase = COR_SEGMENTO1 if estado.fase == 1 else COR_SEGMENTO2
        linha(fase_txt, cor_fase, 0.55, 2)
        linha(f"Plantula atual: #{estado.numero_atual}")

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
        linha(f"Plantulas salvas: {len(estado.plantulas)}")
        linha("ENTER=proxima | Z=desfazer | R=reset", (180,180,180))
        linha("S=salvar | +=zoom+ | -=zoom- | Q=sair", (180,180,180))

    if estado.calibrado:
        txt = f"Calibracao: {estado.mm_por_px*1000:.4f} mm/px  ({estado.cal_mm:.1f}mm ref)"
        cv2.putText(canvas, txt, (10, hud_h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,220,100), 1)
    else:
        cv2.putText(canvas, "Sem calibracao", (10, hud_h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80,80,200), 1)

    cv2.putText(canvas, f"Zoom: {estado.zoom:.1f}x", (hud_w-120, hud_h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

def mouse_callback(event, x, y, flags, estado: Estado):
    if event == cv2.EVENT_MOUSEWHEEL:
        fator = 1.12 if flags > 0 else 1/1.12
        aplicar_zoom(estado, fator, x, y)
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
        ix = max(0, min(ix, estado.w_orig-1))
        iy = max(0, min(iy, estado.h_orig-1))

        if estado.modo == "calibracao":
            if len(estado.cal_pts) < 2:
                estado.cal_pts.append((ix, iy))
            return

        if estado.fase == 1:
            estado.pontos_seg1.append((ix, iy))
        else:
            estado.pontos_seg2.append((ix, iy))

def aplicar_zoom(estado, fator, cx, cy):
    novo_zoom = max(0.2, min(estado.zoom * fator, 10.0))
    estado.offset_x = int(cx - (cx - estado.offset_x) * (novo_zoom / estado.zoom))
    estado.offset_y = int(cy - (cy - estado.offset_y) * (novo_zoom / estado.zoom))
    estado.zoom = novo_zoom

def salvar_resultados(estado: Estado):
    if not estado.plantulas:
        print("[AVISO] Nenhuma plantula para salvar.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base      = os.path.splitext(estado.img_nome)[0]
    dir_out   = os.path.dirname(estado.img_path) or "."

    img_out = estado.img_original.copy()
    for p in estado.plantulas:
        for i in range(1, len(p["pontos_seg1"])):
            cv2.line(img_out, p["pontos_seg1"][i-1], p["pontos_seg1"][i], COR_SEGMENTO1, 4, cv2.LINE_AA)
        for i in range(1, len(p["pontos_seg2"])):
            cv2.line(img_out, p["pontos_seg2"][i-1], p["pontos_seg2"][i], COR_SEGMENTO2, 4, cv2.LINE_AA)
        for pt in p["pontos_seg1"]:
            cv2.circle(img_out, pt, 10, COR_SEGMENTO1, -1)
        for pt in p["pontos_seg2"]:
            cv2.circle(img_out, pt, 10, COR_SEGMENTO2, -1)
        if p["pontos_seg1"]:
            cv2.circle(img_out, p["pontos_seg1"][0],  14, COR_TOPO,    3)
            cv2.circle(img_out, p["pontos_seg1"][-1], 14, COR_ESTRANG, 3)
        if p["pontos_seg2"]:
            cv2.circle(img_out, p["pontos_seg2"][-1], 14, COR_EXTREMIDADE, 3)
        if p["pontos_seg1"]:
            cv2.putText(img_out, f"P{p['numero']}", 
                        (p["pontos_seg1"][0][0]+12, p["pontos_seg1"][0][1]-12),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,255), 3)

    img_path_out = os.path.join(dir_out, f"{base}_anotado_{timestamp}.png")
    cv2.imwrite(img_path_out, img_out)
    print(f"[OK] Imagem anotada salva: {img_path_out}")

    txt_path = os.path.join(dir_out, f"{base}_resultados_{timestamp}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("RELATÓRIO - ANÁLISE DE PLÂNTULAS DE ALFACE\n")
        f.write(f"Imagem: {estado.img_nome}\n")
        f.write(f"Data/hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        if estado.calibrado:
            f.write(f"Calibração: {estado.mm_por_px*1000:.5f} mm/px (referência: {estado.cal_mm:.1f}mm)\n")
        else:
            f.write("Calibracao: não realizada (medidas apenas em pixels)\n")
        f.write("=" * 60 + "\n\n")

        if estado.calibrado:
            f.write(f"{'Plântula':<10} {'Seg1 (px)':<12} {'Seg1 (mm)':<12} {'Seg2 (px)':<12} {'Seg2 (mm)':<12} {'Total (px)':<12} {'Total (mm)':<12}\n")
            f.write("-" * 84 + "\n")
        else:
            f.write(f"{'Plântula':<10} {'Seg1 (px)':<12} {'Seg2 (px)':<12} {'Total (px)':<12}\n")
            f.write("-" * 48 + "\n")

        for p in estado.plantulas:
            if estado.calibrado:
                f.write(f"{'P'+str(p['numero']):<10} {p['seg1_px']:<12.1f} {p['seg1_mm']:<12.2f} {p['seg2_px']:<12.1f} {p['seg2_mm']:<12.2f} {p['total_px']:<12.1f} {p['total_mm']:<12.2f}\n")
            else:
                f.write(f"{'P'+str(p['numero']):<10} {p['seg1_px']:<12.1f} {p['seg2_px']:<12.1f} {p['total_px']:<12.1f}\n")

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

    json_path = os.path.join(dir_out, f"{base}_dados_{timestamp}.json")
    dados = {
        "imagem": estado.img_nome,
        "timestamp": timestamp,
        "calibracao": {
            "realizada": estado.calibrado,
            "mm_por_px": estado.mm_por_px,
            "referencia_mm": estado.cal_mm,
        },
        "plantulas": estado.plantulas,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    print(f"[OK] Dados JSON salvos: {json_path}")

    return img_path_out, txt_path