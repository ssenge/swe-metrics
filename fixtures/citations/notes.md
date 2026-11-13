# Notes

- BR-1: negative ids are refused (`src/Api.java:5`): `if (id < 0)`
- BR-2: the refusal names the cause (`src/Api.java:5`): `if (id < 0) {      throw new IllegalArgumentException`
- BR-3: a file that is gone `src/Gone.java:10`, quoting `x`
- BR-4: past the end of the file `src/Api.java:99`, quoting `return store.load(id);`
- BR-5: a paraphrase of the line `src/Api.java:8`: `fetches the order`
- BR-6: the legacy rule `Old.vb:2`: `If total > limit Then`
- BR-7: a path out of the code `../outside.txt:1`

Not citations: http://localhost:8080/x and example.com:8080 and version 1.2:3.

```
src/Api.java:77 stands in a fence and counts nowhere
```
