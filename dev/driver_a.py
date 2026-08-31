
# ------------------------------------------------------------ entry point --

if __name__ == "__main__":
    instance = parse_input(sys.argv[1])
    output_path = sys.argv[2]

    # T is enforced per instance, so leave a margin for interpreter start-up
    # and the final write. Part A is scored on actual runtime, not on budget
    # used, so this is only a ceiling -- solve_part_a returns the moment a
    # roster verifies.
    budget = max(1.0, 0.9 * instance.T)
    roster, _ = solve_part_a(instance, deadline=time.monotonic() + budget)

    if roster is None:
        write_solution(output_path, {})
    else:
        write_solution(output_path, roster_to_dict(instance, roster))
