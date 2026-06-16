# parquet_info

Utility da terminale per ispezionare file Parquet senza aprire Power BI o caricare manualmente i dati in notebook.

## Esempi rapidi

```powershell
.\parquet_info.cmd *.parquet
```

Mostra metadata, schema e prime righe con output `rich` se disponibile.

```powershell
.\parquet_info.cmd GiacenzeLotti.parquet --profile --columns Codart,Desart,Esistenza,Lotto
```

Calcola null, distinct, range/media e valori piu' frequenti per le colonne indicate.

```powershell
.\parquet_info.cmd GiacenzeLotti.parquet --search REVISORI --columns Desart,Codart,Lotto
```

Cerca testo nelle colonne selezionate e mostra le prime righe trovate.

```powershell
.\parquet_info.cmd *.parquet --format json --pretty-json
```

Esporta un report JSON valido; con piu' file produce un array.

```powershell
.\parquet_info.cmd BaseDWH.parquet --browse
```

Apre il browser interattivo da terminale con frecce/WASD, PagSu/PagGiu e `Q` per uscire.

## Caricamento piu' rapido

Per controllare velocemente metadata e schema senza anteprima righe:

```powershell
.\parquet_info.cmd BaseDWH.parquet --schema-only --format plain
```

Per un'anteprima rapida evita il profilo completo e limita righe/colonne:

```powershell
.\parquet_info.cmd BaseDWH.parquet -n 5 --max-sample-columns 10 --format plain
```

Il profilo completo (`--profile`) e' la parte piu' costosa perche' calcola distinct, range e top valori. Se serve solo un controllo veloce, limita colonne e righe:

```powershell
.\parquet_info.cmd BaseDWH.parquet --profile --profile-rows 50000 --columns Prodotto,Cliente_forn,Valore_fatturato
```

## Dipendenze

```powershell
pip install -r requirements.txt
```

`rich` e' opzionale a runtime: se manca, lo script torna automaticamente all'output plain.
