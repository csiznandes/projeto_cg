import cv2
import numpy as np
import csv
import math
import os
from PIL import Image
import pillow_heif

#Registra o suporte a arquivos HEIC/HEIF do iPhone
pillow_heif.register_heif_opener()

#CONFIGURAÇÕES E VARIÁVEIS GLOBAIS
#Alterar tipo de imagem
NOME_IMAGEM = 'Img/IMG_3196.png' 

pontos_plantula = []
plantulas_medidas = []
contador_plantula = 1

escala_pixels = 0.0
escala_calibrada = False
pontos_regua = []

#FUNÇÃO AUXILIAR: BUSCA DE CAMINHO REAL (ALGORITMO DE VIZINHANÇA)
def calcular_caminho_real(esqueleto, p1, p2):
    pixels_esqueleto = np.argwhere(esqueleto == 255)
    pixels_esqueleto = [tuple(p[::-1]) for p in pixels_esqueleto]

    if not pixels_esqueleto:
        return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

    inicio = min(pixels_esqueleto, key=lambda p: math.hypot(p[0] - p1[0], p[1] - p1[1]))
    fim = min(pixels_esqueleto, key=lambda p: math.hypot(p[0] - p2[0], p[1] - p2[1]))

    fila = [[inicio]]
    visitados = set([inicio])

    while fila:
        caminho = fila.pop(0)
        atual = caminho[-1]

        if atual == fim:
            comprimento_pixels = 0.0
            for i in range(len(caminho) - 1):
                pt1, pt2 = caminho[i], caminho[i+1]
                comprimento_pixels += math.hypot(pt2[0] - pt1[0], pt2[1] - pt1[1])
            return comprimento_pixels

        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                vizinho = (atual[0] + dx, atual[1] + dy)
                if vizinho in pixels_esqueleto and vizinho not in visitados:
                    visitados.add(vizinho)
                    fila.append(caminho + [vizinho])

    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

#FUNÇÃO DE CALLBACK DO MOUSE
def gerenciar_cliques(event, x, y, flags, param):
    global pontos_regua, escala_pixels, escala_calibrada, pontos_plantula, contador_plantula, img_visualizacao

    if event == cv2.EVENT_LBUTTONDOWN:
        if not escala_calibrada:
            pontos_regua.append((x, y))
            cv2.circle(img_visualizacao, (x, y), 5, (255, 0, 0), -1)
            cv2.imshow("Trabalho PI - Computacao Grafica", img_visualizacao)
            
            if len(pontos_regua) == 2:
                dist_pixels = math.hypot(pontos_regua[1][0] - pontos_regua[0][0], pontos_regua[1][1] - pontos_regua[0][1])
                escala_pixels = dist_pixels / 10.0 
                escala_calibrada = True
                print(f"[INFO] Escala Calibrada! 1 pixel = {1.0/escala_pixels:.4f} mm")
                print("\n--- Selecione as estruturas da plantula ---")
                print("Clique 1 (Verde): Topo da estrutura branca")
                print("Clique 2 (Amarelo): Ponto de estrangulamento")
                print("Clique 3 (Vermelho): Fim da raiz")
        else:
            pontos_plantula.append((x, y))
            fase = len(pontos_plantula)
            
            cor = (0, 255, 0) if fase == 1 else (0, 255, 255) if fase == 2 else (0, 0, 255)
            cv2.circle(img_visualizacao, (x, y), 6, cor, -1)
            cv2.putText(img_visualizacao, f"P{contador_plantula}.{fase}", (x + 10, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor, 1)
            cv2.imshow("Trabalho PI - Computacao Grafica", img_visualizacao)

            if len(pontos_plantula) == 3:
                topo, estrangulamento, final_raiz = pontos_plantula
                
                pixels_seg1 = calcular_caminho_real(img_esqueleto, topo, estrangulamento)
                pixels_seg2 = calcular_caminho_real(img_esqueleto, estrangulamento, final_raiz)
                
                mm_seg1 = pixels_seg1 / escala_pixels
                mm_seg2 = pixels_seg2 / escala_pixels
                mm_total = mm_seg1 + mm_seg2
                
                cv2.line(img_visualizacao, topo, estrangulamento, (255, 255, 0), 2)
                cv2.line(img_visualizacao, estrangulamento, final_raiz, (0, 165, 255), 2)
                cv2.putText(img_visualizacao, f"P{contador_plantula}: {mm_total:.1f}mm", (topo[0] - 20, topo[1] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                cv2.imshow("Trabalho PI - Computacao Grafica", img_visualizacao)
                
                plantulas_medidas.append({
                    'id': f"Plantula {contador_plantula:02d}",
                    'seg1_mm': round(mm_seg1, 2),
                    'seg2_mm': round(mm_seg2, 2),
                    'total_mm': round(mm_total, 2)
                })
                
                print(f"[SUCESSO] P{contador_plantula:02d} -> Seg1: {mm_seg1:.2f}mm | Seg2: {mm_seg2:.2f}mm | Total: {mm_total:.2f}mm")
                
                pontos_plantula = []
                contador_plantula += 1

#FLUXO PRINCIPAL DO PROGRAMA
def main():
    global img_esqueleto, img_visualizacao
    
    #Verifica a existência real do arquivo antes de tentar abrir
    if not os.path.exists(NOME_IMAGEM):
        print(f"[ERRO] Arquivo nao encontrado em: '{NOME_IMAGEM}'")
        print("Verifique se as letras maiusculas/minusculas estao exatamente iguais ao nome da pasta.")
        return

    print(f"[PROCESSAMENTO] Carregando imagem: {NOME_IMAGEM}...")
    
    #Tratamento Nativo de arquivos .HEIC do iPhone
    if NOME_IMAGEM.lower().endswith('.heic'):
        img_pil = Image.open(NOME_IMAGEM)
        img_original = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    else:
        img_original = cv2.imread(NOME_IMAGEM)

    #Redimensionamento dinâmico para caber na tela do monitor (25% do tamanho de fábrica)
    largura = int(img_original.shape[1] * 0.25)
    altura = int(img_original.shape[0] * 0.25)
    img_original = cv2.resize(img_original, (largura, altura), interpolation=cv2.INTER_AREA)

    #Pré-processamento Adaptativo para ressaltar as linhas finas da raiz
    img_cinza = cv2.cvtColor(img_original, cv2.COLOR_BGR2GRAY)
    img_suavizada = cv2.GaussianBlur(img_cinza, (3, 3), 0)
    img_binaria = cv2.adaptiveThreshold(
        img_suavizada, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 21, 4
    )
    img_esqueleto = cv2.ximgproc.thinning(img_binaria)

    img_visualizacao = img_original.copy()
    
    cv2.namedWindow("Trabalho PI - Computacao Grafica", cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback("Trabalho PI - Computacao Grafica", gerenciar_cliques)
    
    print(" PASSO 1: CALIBRACAO DA ESCALA DA REGUA")
    print(" Clique em dois riscos da regua que correspondam a exatamente 10mm (1cm)")
    
    while True:
        cv2.imshow("Trabalho PI - Computacao Grafica", img_visualizacao)
        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord('q') or tecla == 27:
            break

    cv2.destroyAllWindows()

    if plantulas_medidas:
        arquivo_csv = 'resultados_medicao_plantulas.csv'
        with open(arquivo_csv, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Identificacao da Plantula', 'Seg. 1: Topo ao Estrangulamento (mm)', 'Seg. 2: Estrangulamento a Raiz (mm)', 'Comprimento Total (mm)'])
            for p in plantulas_medidas:
                writer.writerow([p['id'], str(p['seg1_mm']).replace('.', ','), str(p['seg2_mm']).replace('.', ','), str(p['total_mm']).replace('.', ',')])
        
        nome_saida_img = 'imagem_analisada_final.jpg'
        cv2.imwrite(nome_saida_img, img_visualizacao)
        
        print("\n========================================= PROCESSO CONCLUIDO =========================================")
        print(f"[SALVO] Imagem final gravada em: '{nome_saida_img}'")
        print(f"[SALVO] Planilha CSV atualizada em: '{arquivo_csv}'")
        print("=======================================================================================================")

if __name__ == '__main__':
    main()