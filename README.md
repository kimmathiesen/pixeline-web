# Pixeline i browseren (Unraid-app)

Kører de gamle Pixeline-spil i browseren på iPad og pc. Bag det ligger en rettet udgave af
[DirPlayer](https://github.com/igorlira/dirplayer-rs) (GPL-3), som afspiller Director-filer.

Imaget indeholder **ingen spilfiler**. Du lægger dine egne ISO-filer i en mappe på Unraid, og
containeren gør dem klar første gang, den starter. Originalerne bliver aldrig ændret.

Status: Kun "Syng, leg og lær" er testet og kan spilles med lyd. De andre spil bliver også
klargjort og vist på listen, men de er ikke afprøvet endnu.

- Image: `ghcr.io/kimmathiesen/pixeline-web:latest`. GitHub Actions bygger det ved hvert push
  til `main` (`.github/workflows/build.yml`).
- Template: `https://raw.githubusercontent.com/kimmathiesen/pixeline-web/main/unraid/pixeline.xml`

## Hvis Unraid ikke kan hente imaget

Pakken `pixeline-web` er offentlig, fordi repoet er det. Hvis Unraid alligevel melder
"unauthorized" eller "denied", så gør pakken offentlig manuelt:

1. Gå til https://github.com/users/kimmathiesen/packages/container/package/pixeline-web
2. **Package settings** → **Change visibility** → **Public**.

## Opret appen på Unraid

1. Åbn Unraid-terminalen (ikonet `>_` øverst til højre) og hent templaten:

   ```bash
   wget -O /boot/config/plugins/dockerMan/templates-user/my-pixeline.xml https://raw.githubusercontent.com/kimmathiesen/pixeline-web/main/unraid/pixeline.xml
   ```

2. Opret mappen til ISO-filerne, og kopiér dine Pixeline-ISO'er derind, fx via
   `\\tower\isos\pixeline`:

   ```bash
   mkdir -p /mnt/user/isos/pixeline
   ```

   Filnavnet bliver spillets titel, fx `Pixeline - Syng, leg og lær.iso`.

3. Gå til **Docker → Add Container**, og vælg **pixeline** i rullemenuen *Template* (under
   *User templates*).

4. Tjek felterne, og tryk **Apply**:

   | Felt | Standard |
   |---|---|
   | WebUI | port `8642` |
   | ISO-mappe | `/mnt/user/isos/pixeline` |
   | Spildata | `/mnt/user/appdata/pixeline` |

Appen ligger nu på Docker-fanen med ikon, WebUI-knap og autostart ligesom en app fra
Community Apps. Første start tager et minuts tid pr. spil, mens ISO'erne pakkes ud. Følg med
i containerens log eller på forsiden.

## Opdatering

Når der er pushet til `main`, og GitHub Actions har bygget færdigt, viser Docker-fanen
"update ready" ved næste tjek. Tryk **Update**. Du kan også trykke **Check for Updates**.

## Spil på iPad

1. Åbn `http://192.168.68.58:8642` i Safari.
2. Tryk på dele-knappen og vælg **Føj til hjemmeskærm**. Så åbner spillet i fuld skærm som en app.
3. Vend iPad'en på langs og tryk **Tryk for at starte**. Det tryk er nødvendigt, for ellers
   tillader iOS ikke lyd.

## Nye spil

- **Nyt spil:** læg ISO'en i ISO-mappen og genstart containeren.
- **Gør et spil klar igen:** slet dets mappe under `/mnt/user/appdata/pixeline/` og genstart.

## Indhold

| Fil | Hvad |
|---|---|
| `server.py` | Webserver: spilliste, afspillerside og spilfiler (tåler forkerte store/små bogstaver i stierne) |
| `prepare.py` | Klargør en ISO: pakker ud, trækker startfilmen ud af .exe, retter Lingo-navne, små bogstaver |
| `player/` | Den rettede DirPlayer. `dirplayer-pixeline.patch` viser ændringerne i forhold til v0.8.1 |
| `unraid/` | Unraid-template og ikon |
| `.github/workflows/build.yml` | Bygger og publicerer imaget til ghcr.io |
| `.gitea/workflows/build.yml` | Samme til en Gitea med Actions-runner (bruges ikke lige nu) |
