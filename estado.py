import cv2
import numpy as np
import os
import math
from PIL import Image

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