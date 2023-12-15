sudo apt update &&
    ~/conda/bin/conda update -n base -c defaults conda -y &&
    ~/conda/bin/conda install -c nvidia -c defaults -c intel -c conda-forge --file /docker/extra_packages.txt --all -y &&
    ~/conda/bin/conda init zsh &&
    ~/conda/bin/conda create -n torch pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia -y &&
    ~/conda/bin/conda install -n torch -c nvidia -c defaults -c intel -c conda-forge --file /docker/extra_packages.txt --all -y &&
    ~/conda/envs/torch/bin/pip install --upgrade tensorflow tensorflow-datasets --no-cache-dir &&
    ~/conda/bin/conda clean --all -y &&
    source ~/conda/bin/activate &&
    . ~/.zshrc
