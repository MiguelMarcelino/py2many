class Foo:
    def bar(self):
        return "a"

if __name__ == "__main__":
    f = Foo()
    b = f.bar()
    assert b == "a"
    print("OK")