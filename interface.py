import cv2  #Processamento de imagens e interface gráfica
import numpy as np  #Manipulação eficiente de matrizes de imagens
import os  #Manipulação de caminhos de arquivos e diretórios
import json  #Exportação dos dados coletados para formato estruturado JSON
import math  #Operações matemáticas básicas
from datetime import datetime  #Geração de marcações de data/hora (timestamps) para os arquivos gerados
from estado import Estado  #Importação da classe de controle de estado interno da aplicação
from config import (COR_SEGMENTO1, COR_SEGMENTO2, COR_TOTAL, COR_PONTO, 
                    COR_ESTRANG, COR_TOPO, COR_EXTREMIDADE, RAIO_PONTO, ESPESSURA_LINHA) #Configurações visuais

def desenhar_frame(estado: Estado):
    """Compõe o frame completo (imagem renderizada + desenhos + HUD) para exibição na janela."""
    
    #Redimensionamento baseado no zoom atual do sistema
    h_vis = int(estado.h_orig * estado.zoom)  #Calcula a nova altura visível com base no zoom
    w_vis = int(estado.w_orig * estado.zoom)  #Calcula a nova largura visível com base no zoom
    #Redimensiona a imagem original usando interpolação linear (suavização)
    img_vis = cv2.resize(estado.img_original, (w_vis, h_vis), interpolation=cv2.INTER_LINEAR)

    #Criação do canvas (fundo escuro de tamanho fixo para a janela)
    canvas = np.zeros((estado.win_h, estado.win_w, 3), dtype=np.uint8)  #Matriz preta de 3 canais (BGR)
    canvas[:] = (40, 40, 40)  #Aplica uma cor cinza escuro de fundo

    #Lógica matemática de Pan/Navegação
    ox, oy = estado.offset_x, estado.offset_y  #Armazena os offsets do arrastar de tela
    x1_src = max(0, -ox);          y1_src = max(0, -oy)  #Garante limites válidos dentro da imagem de origem
    x2_src = min(w_vis, estado.win_w - ox)
    y2_src = min(h_vis, estado.win_h - oy)
    x1_dst = max(0, ox);           y1_dst = max(0, oy)   #Define onde a imagem começará a ser colada no canvas final
    x2_dst = x1_dst + (x2_src - x1_src)
    y2_dst = y1_dst + (y2_src - y1_src)

    #Se a área calculada for válida, copia a sub-região da imagem ampliada para o canvas
    if x2_src > x1_src and y2_src > y1_src:
        canvas[y1_dst:y2_dst, x1_dst:x2_dst] = img_vis[y1_src:y2_src, x1_src:x2_src]

    #Desenho das plântulas que já foram salvas anteriormente
    for p in estado.plantulas:
        _desenhar_segmento(canvas, estado, p["pontos_seg1"], COR_SEGMENTO1)  #Desenha o Segmento 1 (Verde)
        _desenhar_segmento(canvas, estado, p["pontos_seg2"], COR_SEGMENTO2)  #Desenha o Segmento 2 (Laranja)
        if p["pontos_seg1"]:
            #Converte a coordenada real da imagem para a posição atual de renderização na tela
            tx, ty = estado.img_para_tela(*p["pontos_seg1"][0])
            #Insere o rótulo de texto (Ex: P1, P2) acima do topo da plântula correspondente
            cv2.putText(canvas, f"P{p['numero']}", (tx+6, ty-6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

    #Desenho dos pontos em tempo real da plântula que está sendo medida agora
    _desenhar_segmento(canvas, estado, estado.pontos_seg1, COR_SEGMENTO1)
    _desenhar_segmento(canvas, estado, estado.pontos_seg2, COR_SEGMENTO2)

    #Se houver um ponto inicial (Topo) na plântula corrente, destaca-o visualmente
    if estado.pontos_seg1:
        tx, ty = estado.img_para_tela(*estado.pontos_seg1[0])
        cv2.circle(canvas, (tx, ty), RAIO_PONTO+2, COR_TOPO, -1)  #Desenha círculo preenchido (-1)
        cv2.putText(canvas, "TOPO", (tx+8, ty-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COR_TOPO, 2)

    #Se o primeiro segmento terminou e o usuário está na Fase 2, desenha o ponto de estrangulamento
    if estado.pontos_seg1 and estado.fase == 2:
        tx, ty = estado.img_para_tela(*estado.pontos_seg1[-1])
        cv2.circle(canvas, (tx, ty), RAIO_PONTO+2, COR_ESTRANG, -1)
        cv2.putText(canvas, "ESTRANG.", (tx+8, ty-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COR_ESTRANG, 2)

    #Se houver pontos no segundo segmento, sinaliza o ponto final na última coordenada registrada
    if estado.pontos_seg2:
        tx, ty = estado.img_para_tela(*estado.pontos_seg2[-1])
        cv2.circle(canvas, (tx, ty), RAIO_PONTO+2, COR_EXTREMIDADE, -1)

    #Renderização visual do Modo de Calibração (Régua)
    if estado.modo == "calibracao":
        for i, pt in enumerate(estado.cal_pts):
            tx, ty = estado.img_para_tela(*pt)
            cv2.circle(canvas, (tx, ty), RAIO_PONTO, (0, 255, 255), -1)  #Desenha os círculos de calibração em amarelo
            label = "A" if i == 0 else "B"  #Define se é a marcação de partida ou de chegada na régua
            cv2.putText(canvas, label, (tx+8, ty-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        #Se os dois pontos da régua já foram selecionados, desenha uma reta amarela entre eles
        if len(estado.cal_pts) == 2:
            tA = estado.img_para_tela(*estado.cal_pts[0])
            tB = estado.img_para_tela(*estado.cal_pts[1])
            cv2.line(canvas, tA, tB, (0, 255, 255), 2, cv2.LINE_AA)  #cv2.LINE_AA cria uma linha suavizada (anti-aliasing)

    #Renderiza o painel textual de dados (HUD) e retorna a imagem construída
    _desenhar_hud(canvas, estado)
    return canvas

def _desenhar_segmento(canvas, estado, pontos, cor):
    """Função auxiliar para conectar listas de coordenadas criando linhas contínuas."""
    if len(pontos) < 2:
        if pontos:  #Se houver apenas 1 ponto isolado, renderiza somente um ponto na tela
            tx, ty = estado.img_para_tela(*pontos[0])
            cv2.circle(canvas, (tx, ty), RAIO_PONTO, cor, -1)
        return
    #Mapeia todas as coordenadas reais da imagem para coordenadas atuais de exibição
    pts_tela = [estado.img_para_tela(*p) for p in pontos]
    #Varre a lista interligando os pontos sequencialmente por retas (representando curvas sinuosas)
    for i in range(1, len(pts_tela)):
        cv2.line(canvas, pts_tela[i-1], pts_tela[i], cor, ESPESSURA_LINHA, cv2.LINE_AA)
    #Desenha pequenos círculos em cima de cada nó da estrutura para evidenciar os cliques do mouse
    for pt in pts_tela:
        cv2.circle(canvas, pt, RAIO_PONTO, cor, -1)

def _desenhar_hud(canvas, estado: Estado):
    """Cria o painel lateral translúcido superior esquerdo contendo informações de diagnóstico e instruções."""
    hud_h, hud_w = canvas.shape[:2]
    overlay = canvas.copy()  #Cria uma cópia do canvas para criar efeito de semitransparência
    cv2.rectangle(overlay, (0, 0), (420, 260), (20, 20, 20), -1)  #Desenha o retângulo escuro do painel
    #Mistura 75% do retângulo escuro com 25% da imagem sob ele, gerando a transparência
    cv2.addWeighted(overlay, 0.75, canvas, 0.25, 0, canvas)

    y = 22  #Posição vertical inicial do texto
    def linha(txt, cor=(220,220,220), escala=0.55, esp=2):
        """Função interna auxiliar para automatizar a quebra de linhas no HUD."""
        nonlocal y
        cv2.putText(canvas, txt, (10, y), cv2.FONT_HERSHEY_SIMPLEX, escala, cor, esp)
        y += 22  #Incrementa a altura para a próxima linha não sobrepor a anterior

    #Sub-painel específico para as instruções de calibração por régua
    if estado.modo == "calibracao":
        linha("CALIBRACAO", (0, 220, 255), 0.65, 2)
        linha("Clique em 2 pontos conhecidos da regua", (200,200,200))
        linha(f"Pontos selecionados: {len(estado.cal_pts)}/2")
        if len(estado.cal_pts) == 2:
            #Aplicação do teorema de Pitágoras para obter a distância euclidiana em pixels
            dx = estado.cal_pts[1][0] - estado.cal_pts[0][0]
            dy = estado.cal_pts[1][1] - estado.cal_pts[0][1]
            dist_px = math.sqrt(dx*dx + dy*dy)
            linha(f"Distancia: {dist_px:.1f} px")
            linha("Digite o valor real (mm) no terminal")
        linha("Z: desfazer ponto | ENTER: confirmar", (180,180,180))
    #Sub-painel específico exibido durante o processo padrão de medição das plântulas
    else:
        linha("MEDICAO", (0, 220, 100), 0.65, 2)
        fase_txt = "Fase 1: Topo -> Estrangulamento" if estado.fase == 1 else "Fase 2: Estrangulamento -> Extremidade"
        cor_fase = COR_SEGMENTO1 if estado.fase == 1 else COR_SEGMENTO2
        linha(fase_txt, cor_fase, 0.55, 2)
        linha(f"Plantula atual: #{estado.numero_atual}")

        #Computa a distância acumulada de pixels percorridos em cada segmento
        seg1_px = estado.comprimento_px(estado.pontos_seg1)
        seg2_px = estado.comprimento_px(estado.pontos_seg2)
        total_px = seg1_px + seg2_px

        #Se já existir calibração válida, exibe os valores convertidos para milímetros (mm)
        if estado.calibrado:
            s1mm  = estado.px_para_mm(seg1_px)
            s2mm  = estado.px_para_mm(seg2_px)
            totmm = estado.px_para_mm(total_px)
            linha(f"Seg1 (verde):   {seg1_px:.0f}px = {s1mm:.2f}mm", COR_SEGMENTO1)
            linha(f"Seg2 (laranja): {seg2_px:.0f}px = {s2mm:.2f}mm", COR_SEGMENTO2)
            linha(f"Total:          {total_px:.0f}px = {totmm:.2f}mm", COR_TOTAL)
        else:  # Caso contrário, exibe os dados temporários brutos em pixels
            linha(f"Seg1 (verde):   {seg1_px:.0f}px", COR_SEGMENTO1)
            linha(f"Seg2 (laranja): {seg2_px:.0f}px", COR_SEGMENTO2)
            linha(f"Total:          {total_px:.0f}px", COR_TOTAL)
        linha("")
        linha(f"Plantulas salvas: {len(estado.plantulas)}")
        linha("ENTER=proxima | Z=desfazer | R=reset", (180,180,180))
        linha("S=salvar | +=zoom+ | -=zoom- | Q=sair", (180,180,180))

    #Barra informativa inferior (Indica se há calibração e a proporção matemática do pixel)
    if estado.calibrado:
        txt = f"Calibracao: {estado.mm_por_px*1000:.4f} mm/px  ({estado.cal_mm:.1f}mm ref)"
        cv2.putText(canvas, txt, (10, hud_h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,220,100), 1)
    else:
        cv2.putText(canvas, "Sem calibracao", (10, hud_h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80,80,200), 1)

    #Exibe a porcentagem do zoom no canto inferior direito da tela
    cv2.putText(canvas, f"Zoom: {estado.zoom:.1f}x", (hud_w-120, hud_h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

def mouse_callback(event, x, y, flags, estado: Estado):
    """Captura e gerencia de forma assíncrona todas as interações do mouse (Cliques, Scroll e Pan)."""
    
    #Evento de Rolar a Roda do Mouse: Aplica Zoom focado no ponteiro
    if event == cv2.EVENT_MOUSEWHEEL:
        fator = 1.12 if flags > 0 else 1/1.12  #Se scroll for positivo, amplia; se negativo, reduz
        aplicar_zoom(estado, fator, x, y)
        return

    #Clique com Botão Direito: Inicializa o arrasto de tela (Pan)
    if event == cv2.EVENT_RBUTTONDOWN:
        estado.pan_inicio         = (x, y)  #Guarda a coordenada inicial do clique
        estado.pan_offset_inicio  = (estado.offset_x, estado.offset_y)  #Guarda o offset atual
        return

    #Movimentação do Mouse com Botão Direito Pressionado: Atualiza Deslocamento da Imagem
    if event == cv2.EVENT_MOUSEMOVE and flags & cv2.EVENT_FLAG_RBUTTON:
        if estado.pan_inicio:
            dx = x - estado.pan_inicio[0]  #Variação no eixo X
            dy = y - estado.pan_inicio[1]  #Variação no eixo Y
            estado.offset_x = estado.pan_offset_inicio[0] + dx  #Aplica o novo offset acumulado
            estado.offset_y = estado.pan_offset_inicio[1] + dy
        return

    #Soltar Botão Direito: Finaliza o ciclo de Pan
    if event == cv2.EVENT_RBUTTONUP:
        estado.pan_inicio = None
        return

    #Clique com Botão Esquerdo: Registro de pontos de medição ou calibração
    if event == cv2.EVENT_LBUTTONDOWN:
        ix, iy = estado.tela_para_img(x, y)  #Converte o clique na janela gráfica para a coordenada real do pixel na matriz original da foto
        ix = max(0, min(ix, estado.w_orig-1))  #Restringe (clamp) para evitar erros fora das bordas da imagem
        iy = max(0, min(iy, estado.h_orig-1))

        #Adiciona pontos na calibração da régua até atingir o limite de 2
        if estado.modo == "calibracao":
            if len(estado.cal_pts) < 2:
                estado.cal_pts.append((ix, iy))
            return

        #Distribui o clique baseado na fase de segmentação
        if estado.fase == 1:
            estado.pontos_seg1.append((ix, iy))  #Incrementa nós no caule inicial
        else:
            estado.pontos_seg2.append((ix, iy))  #Incrementa nós na estrutura

def aplicar_zoom(estado, fator, cx, cy):
    """Calcula matematicamente o novo fator de escala mantendo o ponto focado estático na tela."""
    novo_zoom = max(0.2, min(estado.zoom * fator, 10.0))  # Limita o zoom entre 0.2x e 10x
    #Ajusta os offsets para que a transição de zoom pareça convergir em direção ao local do cursor do mouse
    estado.offset_x = int(cx - (cx - estado.offset_x) * (novo_zoom / estado.zoom))
    estado.offset_y = int(cy - (cy - estado.offset_y) * (novo_zoom / estado.zoom))
    estado.zoom = novo_zoom

def salvar_resultados(estado: Estado):
    """Exporta de maneira definitiva três arquivos: a imagem anotada (.png), relatório (.txt) e dados puros (.json)."""
    if not estado.plantulas:
        print("[AVISO] Nenhuma plantula para salvar.")
        return

    #Geração de nomenclatura automática única baseada no nome da imagem de entrada e data/hora
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base      = os.path.splitext(estado.img_nome)[0]
    dir_out   = os.path.dirname(estado.img_path) or "."

    #PARTE 1: Exportar Imagem de Saída Anotada pelo usuário
    img_out = estado.img_original.copy()  #Cria cópia limpa da foto original para desenhar direto na resolução cheia
    for p in estado.plantulas:
        #Redesenha de maneira mais espessa as linhas do Segmento 1
        for i in range(1, len(p["pontos_seg1"])):
            cv2.line(img_out, p["pontos_seg1"][i-1], p["pontos_seg1"][i], COR_SEGMENTO1, 4, cv2.LINE_AA)
        #Redesenha de maneira mais espessa as linhas do Segmento 2
        for i in range(1, len(p["pontos_seg2"])):
            cv2.line(img_out, p["pontos_seg2"][i-1], p["pontos_seg2"][i], COR_SEGMENTO2, 4, cv2.LINE_AA)
        #Pontua individualmente os nós de cliques armazenados
        for pt in p["pontos_seg1"]:
            cv2.circle(img_out, pt, 10, COR_SEGMENTO1, -1)
        for pt in p["pontos_seg2"]:
            cv2.circle(img_out, pt, 10, COR_SEGMENTO2, -1)
        #Circunda com anéis o Topo e o Ponto de Estrangulamento
        if p["pontos_seg1"]:
            cv2.circle(img_out, p["pontos_seg1"][0],  14, COR_TOPO,    3)
            cv2.circle(img_out, p["pontos_seg1"][-1], 14, COR_ESTRANG, 3)
        #Circunda com anéis a Extremidade final da raiz
        if p["pontos_seg2"]:
            cv2.circle(img_out, p["pontos_seg2"][-1], 14, COR_EXTREMIDADE, 3)
        #Adiciona a identificação textual em escala maior na foto de alta qualidade
        if p["pontos_seg1"]:
            cv2.putText(img_out, f"P{p['numero']}", 
                        (p["pontos_seg1"][0][0]+12, p["pontos_seg1"][0][1]-12),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,255), 3)

    img_path_out = os.path.join(dir_out, f"{base}_anotado_{timestamp}.png")
    cv2.imwrite(img_path_out, img_out)  #Grava fisicamente a imagem modificada no disco rígido
    print(f"[OK] Imagem anotada salva: {img_path_out}")

    #PARTE 2: Exportar Relatório de Texto
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

        #Cabeçalhos formatados com espaçamento fixo
        if estado.calibrado:
            f.write(f"{'Plântula':<10} {'Seg1 (px)':<12} {'Seg1 (mm)':<12} {'Seg2 (px)':<12} {'Seg2 (mm)':<12} {'Total (px)':<12} {'Total (mm)':<12}\n")
            f.write("-" * 84 + "\n")
        else:
            f.write(f"{'Plântula':<10} {'Seg1 (px)':<12} {'Seg2 (px)':<12} {'Total (px)':<12}\n")
            f.write("-" * 48 + "\n")

        # Varre e escreve a linha de cada plântula individualmente
        for p in estado.plantulas:
            if estado.calibrado:
                f.write(f"{'P'+str(p['numero']):<10} {p['seg1_px']:<12.1f} {p['seg1_mm']:<12.2f} {p['seg2_px']:<12.1f} {p['seg2_mm']:<12.2f} {p['total_px']:<12.1f} {p['total_mm']:<12.2f}\n")
            else:
                f.write(f"{'P'+str(p['numero']):<10} {p['seg1_px']:<12.1f} {p['seg2_px']:<12.1f} {p['total_px']:<12.1f}\n")

        #Cálculos (Cálculo automático de Médias, Máximos e Mínimos via NumPy)
        f.write("\n" + "=" * 60 + "\n")
        f.write("ESTATÍSTICAS\n")
        f.write("-" * 60 + "\n")
        totais_px = [p["total_px"] for p in estado.plantulas]
        f.write(f"Nº de plântulas medidas: {len(estado.plantulas)}\n")
        f.write(f"Total médio (px): {np.mean(totais_px):.1f}\n")  #np.mean calcula a média aritmética da lista
        if estado.calibrado:
            totais_mm = [p["total_mm"] for p in estado.plantulas]
            f.write(f"Total médio (mm): {np.mean(totais_mm):.2f}\n")
            f.write(f"Total mínimo (mm): {min(totais_mm):.2f}\n")  #Identifica a menor plântula do lote
            f.write(f"Total máximo (mm): {max(totais_mm):.2f}\n")  #Identifica a maior plântula do lote

    print(f"[OK] Relatório salvo: {txt_path}")

    #PARTE 3: Exporta Banco de Dados estruturado em JSON
    json_path = os.path.join(dir_out, f"{base}_dados_{timestamp}.json")
    dados = {
        "imagem": estado.img_nome,
        "timestamp": timestamp,
        "calibracao": {
            "realizada": estado.calibrado,
            "mm_por_px": estado.mm_por_px,
            "referencia_mm": estado.cal_mm,
        },
        "plantulas": estado.plantulas,  #Salva todas as coordenadas de pontos para remontar o estado se necessário
    }
    with open(json_path, "w", encoding="utf-8") as f:
        #Serializa e salva o dicionário formatando recuos em 2 espaços e preservando caracteres especiais
        json.dump(dados, f, indent=2, ensure_ascii=False)
    print(f"[OK] Dados JSON salvos: {json_path}")

    return img_path_out, txt_path  #Retorna os caminhos dos arquivos gerados para controle do fluxo principal