import hassapi as hass
import aiohttp
import datetime
from datetime import date

class VareFetcher(hass.Hass):

    async def initialize(self):
        self.log("Väre Data Fetcher käynnistyi onnistuneesti.")      
        
        # Ajetaan ensimmäinen haku välittömästi taustalla
        self.create_task(self.fetch_data({}))
        
        # Ajastetaan toistuvat haut yksinkertaisesti AppDaemonin omilla ajastimilla
        self.run_hourly(self.fetch_data, datetime.time(0, 1, 0))
        self.run_hourly(self.fetch_data, datetime.time(0, 16, 0))
        self.run_hourly(self.fetch_data, datetime.time(0, 31, 0))
        self.run_hourly(self.fetch_data, datetime.time(0, 46, 0))
        
        self.log("Ajastimet asetettu: haku tapahtuu tunnin sisällä minuuteilla 01, 16, 31 ja 46.")

    async def fetch_data(self, kwargs):
        username = self.args.get("username")
        password = self.args.get("password")
        gsrn_input = self.args.get("gsrn")
        
        # Varmistetaan, että gsrn käsitellään listana (vaikka käyttäjä antaisi vain yhden)
        if isinstance(gsrn_input, str) or isinstance(gsrn_input, int):
            gsrn_list = [str(gsrn_input)]
        elif isinstance(gsrn_input, list):
            gsrn_list = [str(g) for g in gsrn_input]
        else:
            self.log("GSRN puuttuu tai on väärässä muodossa apps.yaml -tiedostossa.", level="ERROR")
            return
            
        summary_url_template = self.args.get("summary_url", "https://vappi.fi/api/v2/servicelocation/user/{user_id}/location/{gsrn}?utilityType=ELECTRICITY")

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Kirjautuminen
                async with session.post("https://vappi.fi/auth/login", 
                                        data={"username": username, "password": password}) as resp:
                    if resp.status != 200:
                        self.log("Kirjautuminen epäonnistui", level="WARNING")
                        return

                # 2. Haetaan automaattinen User ID
                async with session.get("https://vappi.fi/api/v2/me") as resp:
                    if resp.status != 200:
                        self.log("Käyttäjätietojen haku epäonnistui", level="WARNING")
                        return
                    me_data = await resp.json()
                    u_id = me_data.get("priwattiId")
                    
                    if not u_id:
                        self.log("Ei saatu haettua priwattiId:tä", level="ERROR")
                        return
                
                tanaan = date.today().isoformat()
                
                # 3. Käydään läpi kaikki määritellyt käyttöpaikat
                for gsrn in gsrn_list:
                    
                    # Jos käyttöpaikkoja on vain 1, pidetään alkuperäiset sensorien nimet
                    # Jos useita, lisätään GSRN sensorin nimeen
                    is_multi = len(gsrn_list) > 1
                    suffix = f"_{gsrn}" if is_multi else ""
                    friendly_suffix = f" ({gsrn[-4:]})" if is_multi else ""
                    
                    summary_url = summary_url_template.format(user_id=u_id, gsrn=gsrn)
                    base_url = f"https://vappi.fi/api/utility-data/v1/user/{u_id}/location/GSRN_{gsrn}"
                    
                    quarterly_url = f"{base_url}/day-quarterly/{tanaan}?type=electricity-invoiced"
                    hourly_url = f"{base_url}/day/{tanaan}?type=electricity-invoiced"

                    # 4. Yleistiedot
                    async with session.get(summary_url) as resp:
                        if resp.status == 200:
                            s_data = await resp.json()
                            mkt = s_data.get("marketPrice", {})
                            inv = s_data.get("secondInvoice", {})
                            
                            self.set_state(f"sensor.vare_summary{suffix}", 
                                           state=s_data.get("energyConsumption", {}).get("yesterdayConsumption", 0), 
                                           attributes={
                                               "unit_of_measurement": "kWh",
                                               "friendly_name": f"Väre Yleistiedot{friendly_suffix}",
                                               "hourly_price_vat": mkt.get("hourlyPriceVat"),
                                               "invoice_amount": inv.get("amount"),
                                               "gsrn": gsrn,
                                               "last_updated": str(datetime.datetime.now())
                                           })

                    # 5. Varttidata
                    async with session.get(quarterly_url) as resp:
                        if resp.status == 200:
                            q_data = await resp.json()
                            q_history = q_data.get("data", [])
                            self.set_state(f"sensor.vare_quarterly{suffix}", 
                                           state=q_history[-1].get("value", 0) if q_history else 0, 
                                           attributes={
                                               "unit_of_measurement": "kWh",
                                               "friendly_name": f"Väre Varttiseuranta{friendly_suffix}",
                                               "daily_total": q_data.get("total"),
                                               "history": q_history,
                                               "gsrn": gsrn,
                                               "last_updated": str(datetime.datetime.now())
                                           })

                    # 6. Tuntidata
                    async with session.get(hourly_url) as resp:
                        if resp.status == 200:
                            h_data = await resp.json()
                            h_history = h_data.get("data", [])
                            self.set_state(f"sensor.vare_hourly{suffix}", 
                                           state=h_history[-1].get("value", 0) if h_history else 0, 
                                           attributes={
                                               "unit_of_measurement": "kWh",
                                               "friendly_name": f"Väre Tuntiseuranta{friendly_suffix}",
                                               "daily_total": h_data.get("total"),
                                               "history": h_history,
                                               "gsrn": gsrn,
                                               "last_updated": str(datetime.datetime.now())
                                           })
                
                self.log(f"Tiedot haettu onnistuneesti käyttäjälle {u_id} ({len(gsrn_list)} käyttöpaikkaa).")

        except Exception as e:
            self.log(f"Virhe haussa: {e}", level="ERROR")
