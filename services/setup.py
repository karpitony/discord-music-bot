import os

def setup():
    if not os.path.exists('music'):
        os.makedirs('music')
        
    gitkeep_path = os.path.join('music', '.gitkeep')
    with open(gitkeep_path, 'w') as gitkeep:
        gitkeep.write('')

    for filename in os.listdir('music'):
        file_path = os.path.join('music', filename)
        if file_path != gitkeep_path:
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                import shutil
                shutil.rmtree(file_path)
        
    