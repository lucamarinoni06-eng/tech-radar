# Tech Radar · Big 7

Dashboard con dati che si aggiornano da soli per Apple, Microsoft, Alphabet, Amazon, Nvidia, Meta e Tesla.
Parte statica (dossier su segmenti, concorrenti, fornitori, norme) in `docs/data/companies.json`.
Parte live (generata da `scripts/fetch.py`): bilanci e filing SEC, brevetti EPO, documenti del Federal Register, news.

## Attivazione in 5 passi
1. Crea un repository su GitHub e carica il contenuto di questa cartella.
2. **Settings → Secrets and variables → Actions**, aggiungi:
   - `SEC_USER_AGENT`: il tuo nome ed email, es. `Mario Rossi mario@example.com` (richiesto da SEC EDGAR).
   - `EPO_KEY` e `EPO_SECRET`: registrati gratis su developers.epo.org e crea un'app (Open Patent Services).
3. **Settings → Pages**: sorgente = ramo principale, cartella `/docs`.
4. **Actions → Aggiorna dati → Run workflow** per il primo aggiornamento; poi parte ogni giorno alle 05:00 UTC.
5. Apri l'indirizzo di GitHub Pages.

## Uso locale
```
export SEC_USER_AGENT="Nome Cognome email"
export EPO_KEY=... EPO_SECRET=...
python scripts/fetch.py            # tutte le aziende (oppure: python scripts/fetch.py NVDA TSLA)
python -m http.server -d docs      # poi apri http://localhost:8000
```
Lo script usa solo la libreria standard di Python.

## Aggiungere un'azienda
Aggiungi un oggetto in `aziende` di `docs/data/companies.json` (ticker, nome, CIK a 10 cifre dalla SEC, nomi dei titolari brevetti, classi CPC, termini per il Federal Register).

## Limiti da conoscere
- Le fonti sono: SEC EDGAR, EPO OPS, Federal Register, Google News RSS. Mancano UE (EUR-Lex), USPTO e Asia: vanno aggiunte come moduli in `fetch.py`.
- Il Federal Register copre solo le norme USA. Per l'UE usa le ricerche su EUR-Lex.
- Se una fonte fallisce, l'errore compare nella pagina e le altre continuano a funzionare.
- Le quote EPO gratuite sono limitate e possono cambiare: controlla le condizioni su epo.org.
- Le API cambiano nel tempo (esempio: PatentsView è stato chiuso nel 2026): se un modulo smette di funzionare, controlla la documentazione ufficiale.
- I conteggi di brevetti sono pubblicazioni, non famiglie, e dipendono dal modo in cui i titolari sono registrati.
- Il dossier statico è scritto a mano: verificalo su bilanci e fonti ufficiali prima di usarlo.
- Il codice non è stato eseguito sulle API reali (nella mia sandbox non erano raggiungibili): al primo avvio controlla gli errori.
