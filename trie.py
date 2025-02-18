from enum import Enum

class Trie():
    # we want:
    ## search a string and return (ideally) a single string that most closely matches
    ## to be able to create everything in one fell swoop, not have to insert everything all at once
    # however, i don't have time to do the space-optimized trie right now, and honestly it doesn't really matter
    # because it's only ever going to hold like 20 strings max

    # words:
    ## deck, did, dog, dogs, doggie, doe, do
    # uncompressed
    #    $
    #    |
    #    d
    #   /|\
    #  e i o
    #  | | |\
    #  c d g e
    #  |   |\
    #  k   s g
    #        |
    #        g
    #        |
    #        i
    #        |
    #        e

    # compressed
    #  (root)
    #    |
    #    d
    #   /|\
    #  e i o
    #  c d |\
    #  k   g e
    #      |\
    #      s g
    #        g
    #        i
    #        e

    # to insert a word = w_0 .. w_i
    # traverse the tree.
    # at each node n = n_0 .. n_j:
    #   if we fully match a child:
    #     follow that edge and repeat
    #   otherwise:
    #     find the last index we match, k
    #     redefine n := n_0 .. n_k (note by definition this is also w_0 .. w_k)
    #     add children n_(k+1) .. n_j and w_(k+1) .. w_i
    # 
  
    class node():
        def __init__(self, depth):
            self.depth = depth
            self.children = {}
            self.is_end = False            

        def __iter__(self):
            yield from self.__iter_helper([])

        def __iter_helper(self, prefix):
            if self.is_end:
                yield "".join(prefix)
            for k,v in self.children.items():
                yield from v.__iter_helper(prefix + [k])
            
        def is_match(self, word):
            node = self.__match(word)
            return node.is_end and node.depth == len(word)

        def __match(self, word):
            if self.depth >= len(word) or word[self.depth] not in self.children:
                return self
            else:
                return self.children[word[self.depth]].__match(word)

        def search(self, word):
            node = self.__match(word)
            yield from node.__iter_helper([x for x in word[:node.depth]])

        def __search(self, word, acc):
            if self.is_end:
                pass
                     
        def add_child(self, word):
            self.__add_child(word)
            
        def __add_child(self, word):
            if self.depth >= len(word):
                self.is_end = True
            elif word[self.depth] in self.children:
                self.children[word[self.depth]].__add_child(word)
            else:
                newnode = Trie.node(self.depth+1)
                self.children[word[self.depth]] = newnode
                newnode.__add_child(word)
    
    def __init__(self):
        self.root = Trie.node(0)

    def __iter__(self):
        yield from self.root

    def __contains__(self, word):
        return self.root.is_match(word)
        
    def insert(self, word):
        self.root.add_child(word)

    def search(self, word):
        return list(self.root.search(word))


# this stuff happens if you run this as a script instead of importing it as a package
if __name__ == "__main__":
    t = Trie()

    words = [
        "admiration",
        "acute",
        "assignment",
        "answer",
        "bottle",
        "back",
        "bulletin",
        "bird",
        "competence",
        "cord",
        "cousin",
        "circle",
        "claim",
        "deck",
        "did",
        "dog",
        "dogs",
        "doggie",
        "doe",
        "do",
    ]

    for x in words:
        t.insert(x)

    #for x in t:
    #    print(x)

    print(len(t.search("doreimi")))

    for x in t.search(""):
        print(x)      
