proc qtest {} {
    set s "This string contains {braces} which must not influence indentation"
    puts $s
    if {$flag} {
        puts nested
    }
}
