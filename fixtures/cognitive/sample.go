// Hand-computed cognitive complexity per function (SonarSource rules), see expected.json.
package main

func chain(a int) int {
	if a == 1 {
		return 1
	} else if a == 2 {
		return 2
	} else {
		return 3
	}
}

func loops(xs []int) int {
outer:
	for _, x := range xs {
		for _, y := range xs {
			if x > 0 && y > 0 || x < 0 {
				continue outer
			}
		}
	}
	return 0
}

func sw(a int) int {
	switch a {
	case 1:
		f := func() int {
			if a > 0 {
				return 1
			}
			return 0
		}
		return f()
	default:
		goto end
	}
end:
	return sw(a - 1)
}
