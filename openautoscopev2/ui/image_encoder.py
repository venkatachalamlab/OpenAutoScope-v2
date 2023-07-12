import os
import base64
from tqdm import tqdm
from PIL import Image
from io import BytesIO

def resize(filename, size, encode_format='PNG'):
    im = Image.open(filename)
    new_im = im.resize(size, Image.Resampling.LANCZOS)
    with BytesIO() as buffer:
        new_im.save(buffer, format=encode_format)
        data = buffer.getvalue()
    return data

def icons_to_base64(folder, size=(64, 64)):    
    names = [f for f in os.listdir(folder) if f.endswith('.png') or f.endswith('.ico') or f.endswith('.gif')]
    outfile = open(os.path.join(folder, 'icons.py'), 'w')
    for icon in tqdm(names, desc="Converting icons to base64: "):
        content = resize(os.path.join(folder, icon), size)
        encoded = base64.b64encode(content)
        variable_name = f"ICON_{icon[:icon.rfind('.')].upper()}"
        outfile.write('{} = {}\n'.format(variable_name, encoded))
    outfile.close()


if __name__ == '__main__':
    icons_to_base64('../icons')