"""
Analisador de Plântulas de Alface
Computação Gráfica - UNISC
Prof. Rafael Peiter

Objetivo: Medir digitalmente o comprimento das estruturas de plântulas
de alface a partir de imagens, utilizando OpenCV.

Uso:
    python main.py <caminho_da_imagem>
"""

#Biblioteca OpenCV
import cv2

#Permite acessar os argumentos passados pela linha de comando
import sys

#Biblioteca para manipulação de caminhos e arquivos
import os

#Biblioteca matemática
import math

#Importa a classe que armazena todo o estado do programa
from estado import Estado

#Importa as funções responsáveis pela interface gráfica
from interface import (
    desenhar_frame,
    mouse_callback,
    aplicar_zoom,
    salvar_resultados
)


#Exibe no terminal as instruções de utilização da etapa de medição
def _imprimir_instrucoes_medicao():

    #Explica a primeira fase
    print("\n  Fase 1 – Clique do TOPO da estrutura branca até o ponto de ESTRANGULAMENTO")

    #Explica que os pontos devem seguir a raiz
    print("           (seguindo o formato real do filamento)")

    #ENTER finaliza a primeira fase
    print("  ENTER  → confirma Fase 1 e inicia Fase 2")

    #Explica a segunda fase
    print("\n  Fase 2 – Clique do ESTRANGULAMENTO até a EXTREMIDADE FINAL da raiz")

    #Explica que deve seguir as curvas
    print("           (incluindo curvas e partes enroladas)")

    #ENTER salva a plântula
    print("  ENTER  → salva a plântula e inicia a próxima")

    #Atalhos disponíveis
    print("\n  Z=desfazer | R=resetar plântula atual | S=salvar | Q=sair\n")


#Função principal do programa
def main():

    #Verifica se foi informado o nome da imagem
    if len(sys.argv) < 2:

        #Exibe como utilizar o programa
        print("Uso: python main.py <caminho_da_imagem>")

        print("\nExemplo:")

        print("  python main.py IMG_3196.png")

        #Encerra a execução
        sys.exit(1)


    #Obtém o argumento informado
    argumento_img = sys.argv[1]

    #Caso o usuário informe somente o nome da imagem,
    #adiciona automaticamente a pasta Img
    if not argumento_img.startswith("Img/") and not os.path.isabs(argumento_img):

        img_path = os.path.join("Img", argumento_img)

    else:

        img_path = argumento_img


    #Título apresentado no terminal
    print("ANALISADOR DE PLÂNTULAS DE ALFACE — UNISC")

    #Mostra qual imagem será utilizada
    print(f"Imagem configurada: {img_path}")


    #Tenta carregar a imagem
    try:

        estado = Estado(img_path)

    except FileNotFoundError as e:

        print(f"[ERRO] {e}")

        sys.exit(1)


    #Mostra tamanho da imagem
    print(f"Tamanho: {estado.w_orig} x {estado.h_orig} px")

    #Calcula o fator de zoom necessário para a imagem caber na janela
    zoom_fit_w = estado.win_w / estado.w_orig

    zoom_fit_h = estado.win_h / estado.h_orig

    #Utiliza o menor zoom para garantir que toda imagem apareça
    estado.zoom = min(zoom_fit_w, zoom_fit_h) * 0.95

    #Centraliza horizontalmente
    estado.offset_x = int((estado.win_w - estado.w_orig * estado.zoom) / 2)

    #Centraliza verticalmente
    estado.offset_y = int((estado.win_h - estado.h_orig * estado.zoom) / 2)


    #Cria a janela
    cv2.namedWindow("Analisador de Plântulas", cv2.WINDOW_NORMAL)

    #Define o tamanho inicial da janela
    cv2.resizeWindow("Analisador de Plântulas",
                     estado.win_w,
                     estado.win_h)

    #Define a função responsável pelos eventos do mouse
    cv2.setMouseCallback(
        "Analisador de Plântulas",
        lambda e, x, y, f, p: mouse_callback(e, x, y, f, estado)
    )


    #Mensagens iniciais de calibração
    print("\nCALIBRAÇÃO")

    print("  1. Clique em dois pontos na régua que você conhece a distância.")

    print("  2. Pressione ENTER para confirmar e informar a distância em mm.")

    print("  3. Pressione Z para desfazer o último ponto.")

    print("  4. Pressione ESC para pular a calibração (medidas em px).\n")


    #Loop principal
    while True:

        #Desenha interface
        frame = desenhar_frame(estado)

        #Mostra a imagem na tela
        cv2.imshow("Analisador de Plântulas", frame)

        #Aguarda uma tecla por 20 ms
        key = cv2.waitKey(20) & 0xFF


        #Sai do programa durante a medição
        if key in (ord('q'), 27) and estado.modo == "medicao":

            break


        #ESC durante calibração ignora a calibração
        if key == 27 and estado.modo == "calibracao":

            print("[INFO] Calibração ignorada. Medidas serão em pixels.")

            estado.modo = "medicao"

            print("\n[MEDIÇÃO INICIADA]")

            _imprimir_instrucoes_medicao()


        #Tecla Z
        if key == ord('z') or key == ord('Z'):

            #Durante calibração remove o último ponto
            if estado.modo == "calibracao":

                if estado.cal_pts:

                    estado.cal_pts.pop()

            #Durante medição desfaz o último ponto clicado
            else:

                estado.desfazer()


        #Tecla R
        if key == ord('r') or key == ord('R'):

            if estado.modo == "medicao":

                #Reinicia a plântula atual
                estado.resetar()

                print(f"[RESET] Plântula #{estado.numero_atual} resetada.")


        #ENTER
        if key == 13 or key == 10:

            #Etapa de calibração
            if estado.modo == "calibracao":

                #Confirma se existem dois pontos
                if len(estado.cal_pts) == 2:

                    #Calcula a distância em pixels
                    dx = estado.cal_pts[1][0] - estado.cal_pts[0][0]

                    dy = estado.cal_pts[1][1] - estado.cal_pts[0][1]

                    dist_px = math.sqrt(dx*dx + dy*dy)

                    try:

                        #Solicita a distância real
                        mm_input = input(
                            f"\nDistância entre os dois pontos em mm "
                            f"(distância em px: {dist_px:.1f}): "
                        )

                        #Converte para número
                        mm_val = float(mm_input.replace(",", "."))

                        #Não permite valores negativos
                        if mm_val <= 0:
                            raise ValueError

                        #Calcula o fator mm/pixel
                        estado.mm_por_px = mm_val / dist_px

                        #Guarda o valor informado
                        estado.cal_mm = mm_val

                        #Marca como calibrado
                        estado.calibrado = True

                        print(
                            f"[OK] Calibração: {dist_px:.1f}px = "
                            f"{mm_val}mm → "
                            f"{estado.mm_por_px*1000:.4f} mm/px"
                        )

                        #Entra no modo de medição
                        estado.modo = "medicao"

                        print("\n[MEDIÇÃO INICIADA]")

                        _imprimir_instrucoes_medicao()

                    #Valor inválido
                    except (ValueError, EOFError):

                        print("[AVISO] Valor inválido, calibração ignorada.")

                        estado.modo = "medicao"

                        _imprimir_instrucoes_medicao()

                else:

                    print(
                        f"[AVISO] Selecione 2 pontos antes de confirmar "
                        f"(selecionados: {len(estado.cal_pts)})."
                    )


            #Etapa de medição
            elif estado.modo == "medicao":

                #Primeira fase
                if estado.fase == 1:

                    #Verifica se há pontos suficientes
                    if len(estado.pontos_seg1) >= 2:

                        print(
                            f"[INFO] Fase 1 concluída com "
                            f"{len(estado.pontos_seg1)} pontos."
                        )

                        print(
                            "  Agora clique do estrangulamento até a extremidade da raiz."
                        )

                        print(
                            "  O primeiro ponto do segmento 2 já foi definido."
                        )

                        #Primeiro ponto do segmento 2
                        estado.pontos_seg2 = [estado.pontos_seg1[-1]]

                        #Vai para fase 2
                        estado.fase = 2

                    else:

                        print(
                            "[AVISO] Clique ao menos 2 pontos no Segmento 1."
                        )

                #Segunda fase
                else:

                    #Finaliza a plântula
                    ok = estado.finalizar_plantula()

                    if ok:

                        p = estado.plantulas[-1]

                        #Mostra os resultados
                        print(f"\n[PLÂNTULA #{p['numero']} SALVA]")

                        print(f"  Seg1: {p['seg1_px']:.1f}px")

                        print(f"  Seg2: {p['seg2_px']:.1f}px")

                        print(f"  Total: {p['total_px']:.1f}px")

                        print(
                            f"\n[INFO] Iniciando plântula #{estado.numero_atual}..."
                        )

                    else:

                        print(
                            "[AVISO] Clique ao menos 2 pontos no Segmento 1."
                        )


        #Zoom +
        if key in (ord('+'), ord('=')):

            aplicar_zoom(
                estado,
                1.2,
                estado.win_w // 2,
                estado.win_h // 2
            )


        #Zoom -
        if key in (ord('-'), ord('_')):

            aplicar_zoom(
                estado,
                1 / 1.2,
                estado.win_w // 2,
                estado.win_h // 2
            )


        #Salva os resultados
        if key == ord('s') or key == ord('S'):

            if estado.modo == "medicao":

                salvar_resultados(estado)


    #Pergunta se deseja salvar antes de sair
    if estado.plantulas:

        try:

            resp = input(
                "\nSalvar resultados antes de sair? [S/n]: "
            ).strip().lower()

            if resp != 'n':

                salvar_resultados(estado)

        except EOFError:

            pass


    #Fecha todas as janelas abertas pelo OpenCV
    cv2.destroyAllWindows()

    print("\nPrograma encerrado.")

if __name__ == "__main__":

    main()