# KBC Parallel

Hackathon prototype for the KBC Tectonic Hackathon. One fictional customer, Alex, can compare the current financial path with buying a car. The page shows consequences and trade-offs. It does not recommend a decision.

All banking figures are synthetic. The projection is deterministic Python; the page only displays the API result.

## Run

```bash
python3 -m app.server
```

Open http://127.0.0.1:8080

## Test

```bash
python3 -m unittest tests.test_simulation
```
