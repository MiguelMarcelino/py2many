
abstract type AbstractColors <: AbstractIntEnum end
abstract type AbstractPermissions <: AbstractIntFlag end
mutable struct Colors <: IntEnum

end

mutable struct Permissions <: IntFlag

end

function show()
color_map = Dict(Colors.RED => "red", Colors.GREEN => "green", Colors.BLUE => "blue")
a = Colors.GREEN
if a == Colors.GREEN
println("green")
else
println("Not green")
end
b = Permissions.R
if b == Permissions.R
println("R")
else
println("Not R")
end
@assert(length(color_map) != 0)
end

function main()
show()
end

main()
