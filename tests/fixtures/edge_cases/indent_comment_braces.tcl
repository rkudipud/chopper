proc example {} {
# PROC XYZ {}{
#   foo
#}
puts "after template comment"

# define_proc_attributes example \
#     -info "wrapped comment"
puts "after backslash comment"

set x 1  ;# inline comment with matched {braces} stays balanced
puts "after inline comment"
}
