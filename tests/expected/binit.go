package main

func bisect_right(data []int, item int) int {
	var low int = 0
	high := len(data)
	for low < high {
		middle := int(((low + high) / 2))
		if item < data[middle] {
			high = middle
		} else {
			low = (middle + 1)
		}
	}
	return low
}

func bin_it(limits []int, data []int) []int {
	bins := []int{0}
	for _, _x := range limits {
		bins = append(bins, 0)
	}
	for _, d := range data {
		bins[bisect_right(limits, d)] += 1
	}
	return bins
}

func main() {
	limits := []int{23, 37, 43, 53, 67, 83}
	data := []int{95, 21, 94, 12, 99, 4, 70, 75, 83, 93, 52, 80, 57, 5, 53, 86, 65, 17, 92, 83, 71, 61, 54, 58, 47, 16, 8, 9, 32, 84, 7, 87, 46, 19, 30, 37, 96, 6, 98, 40, 79, 97, 45, 64, 60, 29, 49, 36, 43, 55}
	if !(bin_it(limits, data) == []int{11, 4, 2, 6, 9, 5, 13}) {
		panic("assert")
	}
}
