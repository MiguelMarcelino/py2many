function main()
l = [1, 2, 3]
b = ["a", "b", "c"]
x = 0
@assert(l[(x + 1 + 1):end] == [2, 3])
x = 1
@assert(b[(x + 1 + 1):end] == ["c"])
output = [1, 2, 3, 4, 5, 6]
start = 1
stop = 3
@assert(output[begin:stop - start] == [1, 2])
@assert(output[end:end] == [6])
@assert(output[end] == 6)
println("OK")
end

main()
