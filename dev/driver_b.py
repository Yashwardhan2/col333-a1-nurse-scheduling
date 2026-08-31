
# ------------------------------------------------------------ entry point --

if __name__ == "__main__":
    instance = parse_input(sys.argv[1])
    output_path = sys.argv[2]

    # Part B is scored on cost first, so unlike Part A it spends the budget --
    # but every improvement is written as it is found, so an unexpected kill
    # still leaves the best roster so far on disk rather than nothing.
    budget = max(1.0, 0.9 * instance.T)
    deadline = time.monotonic() + budget

    written = [None]

    def publish(roster, cost):
        if written[0] is None or cost < written[0]:
            written[0] = cost
            write_solution(output_path, roster_to_dict(instance, roster))

    roster, _ = solve_part_b(instance, deadline, on_improve=publish)

    if roster is None:
        write_solution(output_path, {})
