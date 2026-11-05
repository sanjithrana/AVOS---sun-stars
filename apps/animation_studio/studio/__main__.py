from .server import main

if __name__ == "__main__":
    print("AVOS Animation Studio → http://127.0.0.1:%s" % __import__("studio.config", fromlist=["PORT"]).PORT, flush=True)
    main()
