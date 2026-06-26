"""
Analisador de Plântulas de Alface
Computação Gráfica - UNISC
Prof. Rafael Peiter

Objetivo: Medir digitalmente o comprimento das estruturas de plântulas
de alface a partir de imagens, utilizando OpenCV.

Uso:
    python main.py <caminho_da_imagem>
"""

import cv2
import sys
import os
import math
from estado import Estado
from interface import desenhar_frame, mouse_callback, aplicar_zoom, salvar_resultados

def _imprimir_instrucoes_medicao():
    print("\n  Fase 1 – Clique do TOPO da estrutura branca até o ponto de ESTRANGULAMENTO")
    print("           (seguindo o formato real do filamento)")
    print("  ENTER  → confirma Fase 1 e inicia Fase 2")
    print("\n  Fase 2 – Clique do ESTRANGULAMENTO até a EXTREMIDADE FINAL da raiz")
    print("           (incluindo curvas e partes enroladas)")
    print("  ENTER  → salva a plântula e inicia a próxima")
    print("\n  Z=desfazer | R=resetar plântula atual | S=salvar | Q=sair\n")

def main():
    if len(sys.argv) < 2:
        print("Uso: python main.py <caminho_da_imagem>")
        print("\nExemplo:")
        print("  python main.py IMG_3196.png")
        sys.exit(1)

    argumento_img = sys.argv[1]
    
    if not argumento_img.startswith("Img/") and not os.path.isabs(argumento_img):
        img_path = os.path.join("Img", argumento_img)
    else:
        img_path = argumento_img

    print("ANALISADOR DE PLÂNTULAS DE ALFACE — UNISC")
    print(f"Imagem configurada: {img_path}")

    try:
        estado = Estado(img_path)
    except FileNotFoundError as e:
        print(f"[ERRO] {e}")
        sys.exit(1)

    print(f"Tamanho: {estado.w_orig} x {estado.h_orig} px")

    zoom_fit_w = estado.win_w / estado.w_orig
    zoom_fit_h = estado.win_h / estado.h_orig
    estado.zoom = min(zoom_fit_w, zoom_fit_h) * 0.95

    estado.offset_x = int((estado.win_w - estado.w_orig * estado.zoom) / 2)
    estado.offset_y = int((estado.win_h - estado.h_orig * estado.zoom) / 2)

    cv2.namedWindow("Analisador de Plântulas", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Analisador de Plântulas", estado.win_w, estado.win_h)
    cv2.setMouseCallback("Analisador de Plântulas", lambda e, x, y, f, p: mouse_callback(e, x, y, f, estado))

    print("\n[CALIBRAÇÃO]")
    print("  1. Clique em dois pontos na régua que você conhece a distância.")
    print("  2. Pressione ENTER para confirmar e informar a distância em mm.")
    print("  3. Pressione Z para desfazer o último ponto.")
    print("  4. Pressione ESC para pular a calibração (medidas em px).\n")

    while True:
        frame = desenhar_frame(estado)
        cv2.imshow("Analisador de Plântulas", frame)
        key = cv2.waitKey(20) & 0xFF

        if key in (ord('q'), 27) and estado.modo == "medicao":
            break

        if key == 27 and estado.modo == "calibracao":
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

        if key == 13 or key == 10:   # ENTER
            if estado.modo == "calibracao":
                if len(estado.cal_pts) == 2:
                    dx = estado.cal_pts[1][0] - estado.cal_pts[0][0]
                    dy = estado.cal_pts[1][1] - estado.cal_pts[0][1]
                    dist_px = math.sqrt(dx*dx + dy*dy)
                    try:
                        mm_input = input(f"\nDistância entre os dois pontos em mm (distância em px: {dist_px:.1f}): ")
                        mm_val = float(mm_input.replace(",", "."))
                        if mm_val <= 0:
                            raise ValueError
                        estado.mm_por_px  = mm_val / dist_px
                        estado.cal_mm     = mm_val
                        estado.calibrado  = True
                        print(f"[OK] Calibração: {dist_px:.1f}px = {mm_val}mm → {estado.mm_por_px*1000:.4f} mm/px")
                        estado.modo = "medicao"
                        print("\n[MEDIÇÃO INICIADA]")
                        _imprimir_instrucoes_medicao()
                    except (ValueError, EOFError):
                        print("[AVISO] Valor inválido, calibração ignorada.")
                        estado.modo = "medicao"
                        _imprimir_instrucoes_medicao()
                else:
                    print(f"[AVISO] Selecione 2 pontos antes de confirmar (selecionados: {len(estado.cal_pts)}).")

            elif estado.modo == "medicao":
                if estado.fase == 1:
                    if len(estado.pontos_seg1) >= 2:
                        print(f"[INFO] Fase 1 concluída com {len(estado.pontos_seg1)} pontos.")
                        print("  Agora clique do estrangulamento até a extremidade da raiz.")
                        print("  O primeiro ponto do segmento 2 já foi definido.")
                        estado.pontos_seg2 = [estado.pontos_seg1[-1]]
                        estado.fase = 2
                    else:
                        print("[AVISO] Clique ao menos 2 pontos no Segmento 1.")
                else:
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
            aplicar_zoom(estado, 1.2, estado.win_w//2, estado.win_h//2)

        if key in (ord('-'), ord('_')):
            aplicar_zoom(estado, 1/1.2, estado.win_w//2, estado.win_h//2)

        if key == ord('s') or key == ord('S'):
            if estado.modo == "medicao":
                salvar_resultados(estado)

    if estado.plantulas:
        try:
            resp = input("\nSalvar resultados antes de sair? [S/n]: ").strip().lower()
            if resp != 'n':
                salvar_resultados(estado)
        except EOFError:
            pass

    cv2.destroyAllWindows()
    print("\nPrograma encerrado.")

if __name__ == "__main__":
    main()