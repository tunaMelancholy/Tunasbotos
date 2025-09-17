def read_githead():
    try:
        Git_Path = '.git/refs/remotes/origin/main'
        with open(Git_Path, 'r') as file:
            return file.read()[:7]
    except:
        return 'unknown'
