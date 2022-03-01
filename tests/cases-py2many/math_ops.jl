
function main()
    s1 = sum([0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
    s2 = fsum([0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
    a = [1, 2, 3, 4]
    a_sum = sum(a)
    @assert(s1 == 0.9999999999999999)
    @assert(a_sum == 10)
    @assert(s2 == 1.0)
    @assert(sin(0) == 0)
    @assert(cos(0) == 1)
    @assert(tan(0) == 0)
    @assert(sin(radians(30)) == 0.49999999999999994)
    @assert(cos(radians(30)) == 0.8660254037844387)
    @assert(tan(radians(30)) == (sqrt(3) / 3))
    @assert(round(12.556, digits = 2) == 12.56)
end

main()
