import pillow_heif

#Registra o suporte a arquivos HEIC/HEIF do iPhone
pillow_heif.register_heif_opener()

#Configurações visuais 
COR_SEGMENTO1   = (0, 200, 0)      #Verde – do topo ao estrangulamento
COR_SEGMENTO2   = (255, 80, 0)     #Laranja – do estrangulamento à extremidade
COR_TOTAL       = (0, 0, 255)      #Vermelho – linha total (apenas HUD)
COR_PONTO       = (255, 255, 0)    #Amarelo – pontos clicados
COR_ESTRANG     = (255, 0, 255)    #Magenta – ponto de estrangulamento
COR_TOPO        = (0, 255, 255)    #Ciano – topo
COR_EXTREMIDADE = (0, 100, 255)    #Laranja-escuro – extremidade final
RAIO_PONTO      = 8
ESPESSURA_LINHA = 3