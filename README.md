# Pixeline i browseren (Docker på Unraid)

Kører de gamle Pixeline-spil i browseren på iPad og pc. Bag det ligger en rettet udgave af
[DirPlayer](https://github.com/igorlira/dirplayer-rs) (GPL-3), som afspiller Director-filer.

Imaget indeholder **ingen spilfiler**. Du lægger dine egne ISO-filer i en mappe på Unraid, og
containeren gør dem klar første gang, den starter. Originalerne bliver aldrig ændret.

Status: Kun "Syng, leg og lær" er testet og kan spilles med lyd. De andre spil bliver også
klargjort og vist på listen, men de er ikke afprøvet endnu.

## 1. Læg filerne på Unraid

1. Kopiér hele mappen `docker` til Unraid, fx til `\\tower\appdata\pixeline-build\`.
2. Kopiér dine ISO-filer til fx `\\tower\isos\pixeline\`. Filnavnet bliver spillets titel,
   fx `Pixeline - Syng, leg og lær.iso`.

## 2. Byg imaget

Åbn Unraid-terminalen (ikonet `>_` øverst til højre) og kør:

```bash
cd /mnt/user/appdata/pixeline-build && docker build -t pixeline-web:latest .
```

## 3. Start containeren

Med **Compose Manager**-pluginet: brug `docker-compose.yml` herfra og ret stierne under
`volumes`, hvis dine mapper hedder noget andet.

Eller direkte i terminalen:

```bash
docker run -d --name pixeline --restart unless-stopped -p 8080:8080 -v /mnt/user/isos/pixeline:/isos:ro -v /mnt/user/appdata/pixeline:/data pixeline-web:latest
```

Eller via **Docker → Add Container** i Unraid:

| Felt | Værdi |
|---|---|
| Repository | `pixeline-web:latest` |
| Port | container `8080` → host `8080` |
| Path | container `/isos` → `/mnt/user/isos/pixeline` (read only) |
| Path | container `/data` → `/mnt/user/appdata/pixeline` |

Det første start tager et minuts tid pr. spil, mens ISO'erne pakkes ud. Følg med i
containerens log eller på forsiden.

## 4. Spil på iPad

1. Åbn `http://<unraid-ip>:8080` i Safari.
2. Tryk på dele-knappen og vælg **Føj til hjemmeskærm**. Så åbner spillet i fuld skærm som en app.
3. Vend iPad'en på langs og tryk **Tryk for at starte**. Det tryk er nødvendigt, for ellers
   tillader iOS ikke lyd.

## Nye spil og opdateringer

- **Nyt spil:** læg ISO'en i ISO-mappen og genstart containeren.
- **Gør et spil klar igen:** slet dets mappe under `/mnt/user/appdata/pixeline/` og genstart.
- **Ny afspiller:** byg imaget igen (trin 2), og start containeren igen.

## Indhold

| Fil | Hvad |
|---|---|
| `server.py` | Webserver: spilliste, afspillerside og spilfiler (tåler forkerte store/små bogstaver i stierne) |
| `prepare.py` | Klargør en ISO: pakker ud, trækker startfilmen ud af .exe, retter Lingo-navne, små bogstaver |
| `player/` | Den rettede DirPlayer. `dirplayer-pixeline.patch` viser ændringerne i forhold til v0.8.1 |
