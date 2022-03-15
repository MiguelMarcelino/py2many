using Classes
abstract type AbstractPerson end
abstract type AbstractStudent <: AbstractPerson end
@class Foo begin

end
function bar(self::AbstractFoo)::Int64
    return baz(self)
end

function baz(self::AbstractFoo)::Int64
    return 10
end

function bar_str(self::AbstractFoo)::String
    return "a"
end

mutable struct Person <: AbstractPerson
    name::String
end
function get_name(self::AbstractPerson)
    return self.name
end

mutable struct Student <: Person
    domain::String
    name::String
    student_number::Int64

    Student(domain::String = "school.student.pt", name::String, student_number::Int64) =
        new(domain, name, student_number)
    Student(domain, name, student_number) = new(domain, name, student_number)
end
function get_name(self::AbstractStudent)
    return "$(self.student_number) - $(self.name)"
end

function main()
    f = Foo()
    b = bar(f)
    @assert(b == 10)
    c = bar_str(f)
    @assert(c == "a")
    p = Person("P")
    s = Student("S", 111111)
    @assert(get_name(p) == "P")
    @assert(get_name(s) == "111111 - S")
    println("OK")
end

main()
