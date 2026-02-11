# Väre / Väppi kulutustiedot (Home Assistant + AppDaemon)

Tämä on AppDaemon-skripti, joka hakee sähkönkulutustiedot arviot Väreen (Väppi-palvelu) rajapinnasta Home Assistantiin.

Projekti on luotu helpottamaan oman energiankulutuksen seurantaa suoraan Home Assistantista ilman manuaalista tiedonkeruuta.

## Ominaisuudet

* **Varttidata (15 min):** Hakee tarkan laskutusperusteisen kulutuksen (sensor: `sensor.vare_quarterly`).
* **Tuntidata:** Hakee tuntikohtaisen kulutuksen (sensor: `sensor.vare_hourly`).
* **Yhteenveto:** Näyttää Väppi-palvelun etusivulla ilmoittama kulutuslukema, pörssisähkön hinnan ja viimeisimmän laskun summan (sensor: `sensor.vare_summary`).
* **Useiden käyttöpaikkojen tuki:** Skripti osaa hakea tiedot automaattisesti useammasta käyttöpaikasta (esim. koti ja mökki) ja luo niille omat yksilöidyt sensorit.

## Vaatimukset

1.  **Home Assistant**
2.  **AppDaemon** -lisäosa asennettuna (löytyy Home Assistantin Add-on Storesta).

## Asennusohje

### 1. Kopioi tiedosto
Lataa tai luo tiedosto `vare_fetcher.py` ja kopioi se Home Assistantin AppDaemon-kansioon:
`config/appdaemon/apps/vare_fetcher.py`

### 2. Määritä asetukset
Avaa tiedosto `config/appdaemon/apps/apps.yaml` ja lisää sinne seuraavat rivit.

**Tärkeää:** Tarvitset käyttöpaikkatunnuksen (GSRN). Se on 18-numeroinen sarja, joka löytyy sähkölaskustasi tai Väppi-sovelluksesta (alkaa yleensä numeroilla `643...`).

```yaml
vare_data_fetcher:
  module: vare_fetcher
  class: VareFetcher
  # --- OMAT TIEDOT ---
  username: "oma.sahkoposti@esimerkki.fi"
  password: "Salasana123"
  # Voit syöttää yhden käyttöpaikan näin:
  # gsrn: "123456789012345678" # Käyttöpaikkatunnus (18 numeroa)
  
  # TAI voit syöttää useita käyttöpaikkoja listana:
  gsrn: 
    - "123456789012345678" # Koti
    - "876543210987654321" # Mökki
  # --- URL-ASETUKSET (Älä muokkaa näitä) ---
  # Skripti täyttää puuttuvat ID:t automaattisesti
  summary_url: "https://vappi.fi/api/v2/servicelocation/user/{user_id}/location/GSRN_{gsrn}?utilityType=ELECTRICITY"
```

### 3. Käynnistä uudelleen
Tallenna tiedosto. AppDaemon lataa muutokset automaattisesti, mutta voit tarvittaessa käynnistää AppDaemon-lisäosan uudelleen.

## Sensorit

Skripti luo automaattisesti seuraavat kolme sensoria Home Assistantiin:

### 1. `sensor.vare_quarterly` (Varttikulutus)
Näyttää tämän päivän kulutuksen 15 minuutin resoluutiolla.
* **Tila (State):** Viimeisimmän valmistuneen 15 min jakson kulutus (kWh).
* **Attribuutit:**
    * `history`: Lista kaikista päivän varttikulutuksista (aikaleima + arvo). Tätä käytetään graafeissa.
    * `daily_total`: Tämän päivän yhteenlaskettu kokonaiskulutus (perustuu haettuun varttidataan).

### 2. `sensor.vare_hourly` (Tuntikulutus)
Näyttää tämän päivän kulutuksen tunnin resoluutiolla.
* **Tila (State):** Viimeisimmän valmistuneen tunnin kulutus (kWh).
* **Attribuutit:**
    * `history`: Lista kaikista päivän tuntikulutuksista.
    * `daily_total`: Tämän päivän yhteenlaskettu kokonaiskulutus (perustuu haettuun tuntidataan).

### 3. `sensor.vare_summary` (Yleistiedot)
Yleisnäkymä kulutukseen ja laskutukseen.
* **Tila (State):** Väppi-palvelun etusivulla ilmoittama kulutuslukema (kWh).
    * Huom: Tämä arvo tulee rajapinnan kentästä `yesterdayConsumption`, mutta se vastaa usein kuluvan päivän tilannetta Väppi-sovelluksessa. Arvo voi erota `vare_quarterly` ja `vare_hourly` -sensorien summasta johtuen Väreen taustajärjestelmien päivitysviiveistä.
* **Attribuutit:**
    * `invoice_amount`: Viimeisimmän laskun summa (€).
    * `hourly_price_vat`: Pörssisähkön sen hetkinen hinta (sis. ALV).

---

## Tietojen esittäminen (Lovelace)
Datan visualisointiin suositellaan ApexCharts Card -korttia (saatavilla HACS:n kautta).

Tässä esimerkki kortista, joka näyttää tämän päivän kulutuksen 15 minuutin tarkkuudella:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Tämän päivän kulutus (15 min)
graph_span: 24h
span:
  start: day
yaxis:
  - id: y1
    decimals: 3
    apex_config:
      labels:
        show: true
apex_config:
  tooltip:
    y:
      format: "###0.000"
series:
  - entity: sensor.vare_quarterly
    name: Kulutus
    data_generator: |
      return entity.attributes.history.map((entry) => {
        return [new Date(entry.timestamp).getTime(), entry.value];
      });
    type: column
    float_precision: 3
    unit: " kWh"
```
  
## Tietojen päivittyminen
Skripti hakee tiedot automaattisesti 15 minuutin välein. Huomioithan kuitenkin seuraavat seikat:

Viive: Sähkönkulutustiedot eivät ole reaaliaikaisia. Ne päivittyvät Home Assistantiin vasta, kun Väre on päivittänyt ne Väppi-palveluun.

Väreen aikataulut: Viive voi vaihdella 15 minuutista tuntiin tai jopa vuorokauteen riippuen Väreen taustajärjestelmistä ja mittaustietojen siirtymisestä. Skripti näyttää aina tuoreimman saatavilla olevan tiedon.

## Vastuuvapaus ja ylläpito
Tämä on yksityishenkilön tekemä epävirallinen integraatio, eikä sillä ole yhteyttä Väre Oy:hyn.

Käyttö omalla vastuulla: Skriptin käyttö tapahtuu täysin käyttäjän omalla vastuulla. Tekijä ei vastaa mahdollisista virheistä tiedoissa tai niiden aiheuttamista ongelmista.

Ylläpito: Tämä on avoimen lähdekoodin harrasteprojekti. Ylläpidän ja päivitän skriptiä omien aikataulujeni puitteissa ("best effort" -periaatteella).


Elinkaari: Projektin kehitys ja ylläpito jatkuu niin kauan kuin olen itse Väreen asiakas ja pystyn todentamaan skriptin toimivuuden. Mikäli vaihdan sähköyhtiötä, en voi taata skriptin toimivuutta tai päivityksiä sen jälkeen.



