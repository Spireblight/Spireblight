FROM = "0.7"
TO = "0.8"

def migrate(*, automatic: bool):
    return False # FIXME


if __name__ == "__main__":
    migrate(automatic=False)
