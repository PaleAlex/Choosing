#imports
from choosing import *
import streamlit as st
from PIL import Image
import pyautogui
import time
import os
from datetime import date, timedelta
os.environ['DISPLAY'] = ':0'

st.set_page_config(layout="wide")
image = Image.open('logo.png')

st.image(image, width=450)

def reset():
    try:
        time.sleep(2)
        pyautogui.hotkey("ctrl","r")
    except:
        time.sleep(2)
        pyautogui.hotkey("command","r")
    else:
        time.sleep(2)
        pyautogui.hotkey('f5')
    return

#inputs

st.sidebar.header('User Input')

username = st.sidebar.text_input('Identificati con una tua mail (non sarà visibile agli altri utenti)', placeholder="e.g. iamcool@coolest.it" )

if not username:
    st.markdown("""

                ##### Ciao a tutti :sunglasses:
                **Vi presento Choosing nella sua versione adolescenziale - aka beta. \
                La sua missione unica e imprescindibile è quella di consigliare a tutti IL ristorante. \
                Non è per nulla democratico; Choosing ne sceglie per voi UNO (e uno solo), avendo cura però di provare a scegliere il migliore. \
                Come fa?**
                
                **Usa due strategie alternative:**
                
                **1. Ricerca per similarità tra gli utenti di Choosing in base ai ristoranti in comune e ai rating assegnati**
                
                **2. Qualora 1. non restituisca un risultato, Choosing sceglie il ristorante migliore basandosi sulle recensioni di Google**
                
                **Il consiglio che deriva da 1. è molto più personalizzato rispetto a quello di 2. ed è il vero orgoglio di Choosing. \
                L'unica condizione affinché si verifichi è la partecipazione attiva di tanti utenti e il passaparola, se credete nei superpoteri di Choosing. \
                Prendete i suoi consigli, andate a mangiare, tornate qua a dare un voto alla vostra esperienza e continuate a giocare. Più si allargherà la community e più sarà divertente. \
                
                Ma non perdiamo altro tempo, identificatevi con una vostra mail nel menù a sinistra e buonappe!**
                
                
                
                ...ah, ehm, ecco, un'ultima cosa. Mantenere e migliorare Choosing ha qualche costo (APIs, server...). \
                Se credete che Choosing sia una bella idea e utile, potete sostenermi con una piccola donazione qua: [Buy me a :coffee:](https://www.buymeacoffee.com/palealex).
                
                Per suggerimenti o per rimanere semplicemente in contatto <a href="mailto:aless.ciocchetti@gmail.com"> scrivimi qua :speech_balloon: </a>
                
                Un SUPER GRAZIE!
                
                """, unsafe_allow_html=True)


elif username == config.root:
    with open('final.csv') as f:
        st.download_button('final', f, mime='text/csv')
    with open('suggests.csv') as f:
        st.download_button('suggests', f, mime='text/csv')
    canc = st.checkbox("cancella file temporanei")
    mydir = "user_temps/"
    filelist = [ f for f in os.listdir(mydir) if f.endswith(".csv") ]
    st.write("numero file temporanei esistenti ", len(filelist))
    to_delete = st.multiselect('Delete', filelist, filelist)

    if canc:
        for f in to_delete:
            os.remove(os.path.join(mydir, f))
            st.write(f)

else:
    with st.sidebar:

        meal = st.multiselect('Cosa vuoi mangiare?', ("Primi piatti", "Pizza", "Street food", "Carne", "Pesce", "Vegetariano/Vegano", "Etnico", "Orientale", "Altro"), ("Primi piatti", "Pizza", "Street food", "Carne", "Pesce", "Vegetariano/Vegano", "Etnico", "Orientale", "Altro"))
        city = st.text_input('Città', placeholder="e.g. Ferrara").capitalize()
        province = st.text_input('Provincia (sigla)', placeholder="e.g. FE", max_chars=2).upper()
        state = st.text_input('Stato', placeholder="e.g. Italia").capitalize()
        border = st.selectbox("Confine di ricerca", ("comune", "provincia"), help="Utile nel caso non esistano match con altri utenti in base alla ricerca effettuata")
        epp = st.slider("Range spesa per persona", 1, 100, (15, 50), help="Utile nel caso di ricerca per similarità con altri utenti")

    if "border" not in st.session_state:
        st.session_state["border"] = border

    if not meal or not city or not province or not state:
        st.write("*Per conoscere il tuo prossimo miglior ristorante, compila tutti i campi del menù laterale. Se invece devi ancora valutare un ristorante in cui sei stato, continua prima qui sotto*")

        #reviewing
        container = st.expander("ECCO I RISTORANTI A CUI POTRESTI LASCIARE UNA VALUTAZIONE")
        with container:
            def user_to_review():
                data = pd.read_csv("suggests.csv", index_col=0, parse_dates=True)
                return data[data["user"] == username].drop_duplicates(keep= 'last').reset_index(drop= True)
            if len(user_to_review()) > 0:
                to_be_reviewed = user_to_review()
                st.dataframe(data=to_be_reviewed.iloc[:, :-1])

                with st.form(key="review"):
                    selected = st.selectbox("Selezionane uno dalla lista", set(to_be_reviewed["name"]))
                    reviewed = to_be_reviewed[to_be_reviewed["name"] == selected].reset_index(drop = True)

                    NUMBER_OF_COLUMNS = 3
                    f, s, t = st.columns(NUMBER_OF_COLUMNS)
                    with f:
                        reviewed_meal = st.selectbox("Cos'hai mangiato? (se hai provato diverse portate, seleziona quella che ti ha convinto maggiormente)", ("Primi piatti", "Pizza", "Street food", "Carne", "Pesce", "Vegetariano/Vegano", "Etnico", "Orientale", "Altro"))
                    with s:
                        reviewed_epp = st.slider('Spesa per persona (circa)', 1, 100, 25)
                    with t:
                        reviewed_rate = st.slider('Valutazione complessiva', 1.0, 10.0, 8.0, 0.1)
                    ok = st.form_submit_button("Invia!")

                if ok:
                    st.balloons()
                    st.success("Grazie per il tuo contributo. Continua a usare Choosing :) ", icon = "✅")
                    reviewed["rate"] = reviewed_rate
                    reviewed["what"] = reviewed_meal.capitalize()
                    reviewed["epp"] = reviewed_epp
                    with open('final.csv', 'a', encoding='utf-8') as f:
                        reviewed.to_csv(f, mode='a', header=f.tell()==0)
                    tendaysago = date.today() - timedelta(10)

                    suggests = pd.read_csv("suggests.csv", index_col=0).reset_index(drop=True)
                    suggests["added"] = pd.to_datetime(suggests["added"], format='%Y-%m-%d').dt.date

                    try:
                        suggests.drop(suggests.index[(suggests['name'] == reviewed['name'][0]) & (suggests['user'] == reviewed['user'][0])], inplace=True)
                    except:
                        pass
                    suggests = suggests[suggests["added"] > tendaysago].reset_index(drop=True)
                    suggests.to_csv("suggests.csv")
                    final = pd.read_csv("final.csv", index_col=0).drop_duplicates(subset=["name", "user", "what"], keep = 'last').reset_index(drop=True)
                    final.to_csv("final.csv")
                    reset()

            else:
                st.write("Non hai nessun ristorante salvato da valutare. Scegline prima uno e, dopo averlo provato, torna qua a valutarlo.")

    else:
        #choosing object
        ch = Choosing(username, meal, city, province, state, epp, border)
        if border != st.session_state["border"]:
            df = (
                ch.read_temp()[0:0]
                .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
            )
            st.session_state["border"] = border

        #suggests

        container = st.expander("TI SVELO IL TUO PROSSIMO MIGLIOR RISTORANTE")
        with container:
            #---------------------------------------------------------------------
            def markdown_and_save(n_rist, type_of_choice):
                if type_of_choice == 'matched':
                    chose = ch.matched_choice(choice = n_rist)
                    st.markdown('''
                        ******Trovato! In base al match con gli altri utenti:******
                        
                        *(se sei già stato in tutte le proposte di Choosing prova a modificare i criteri di ricerca, oppure torna nel migliore e assaggia qualcosa di nuovo!)*
                        ''')
                else:
                    chose, latlon = ch.random_choice(choice = n_rist)

                    st.markdown('''
                            ******Non ci sono suggerimenti per questa zona in base a similarità con altri utenti. Ecco uno dei migliori ristoranti selezionato secondo le recensioni di Google:******
                            ''')
                    st.map(latlon, zoom = 13)

                html_str = f"""
                                <div style ="text-align: center;" >
                                    <h3>
                                        {chose.iloc[:,0][0]}
                                    </h3>
                                    <h6>
                                        {chose.iloc[:,1][0]} 
                                        <br>
                                    </h6>
                                </div>
                                <br>                    
                                """
                return html_str, chose

            #---------------------------------------------------------------

            try:
                alt = len(ch.matched_suggests())
                if alt == 1:
                    n_rist = 0
                    html, chose = markdown_and_save(n_rist, type_of_choice="matched")
                    st.markdown(html, unsafe_allow_html=True)
                    ok = st.checkbox("Ok, scelgo questo!")

                    if ok:
                        st.balloons()
                        st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")
                        with open('suggests.csv', 'a', encoding='utf-8') as f:
                            chose.to_csv(f, mode='a', header=f.tell() == 0, encoding='utf-8')
                        df = (
                            ch.read_temp()[0:0]
                            .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                        )
                        del st.session_state["border"]
                        reset()

                elif alt > 1:
                    already = st.checkbox("Ci sono già stato, dimmene un altro")
                    if already:
                        disabled = False
                    else:
                        disabled = True

                    rist_slider = st.select_slider(
                        'Ecco delle alternative in ordine decrescente di punteggio di match',
                        options=np.arange(1, alt+1, 1), disabled = disabled)

                    n_rist = rist_slider - 1
                    html, chose = markdown_and_save(n_rist, type_of_choice="matched")

                    st.markdown(html, unsafe_allow_html=True)
                    ok = st.checkbox("Ok, scelgo questo!")

                    if ok:
                        st.balloons()
                        st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")
                        with open('suggests.csv', 'a', encoding='utf-8') as f:
                            chose.to_csv(f, mode='a', header=f.tell() == 0, encoding='utf-8')
                        df = (
                            ch.read_temp()[0:0]
                            .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                        )
                        del st.session_state["border"]
                        reset()

                else:
                    raise Exception("...")

            except:
                alt = len(ch.random_restaurants())

                if alt == 1:
                    n_rist = 0
                    html, chose = markdown_and_save(n_rist, type_of_choice="random")

                    st.markdown(html, unsafe_allow_html=True)
                    ok = st.checkbox("Ok, scelgo questo!")

                    if ok:
                        st.balloons()
                        st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")
                        with open('suggests.csv', 'a', encoding='utf-8') as f:
                            chose.to_csv(f, mode='a', header=f.tell() == 0, encoding='utf-8')
                        df = (
                            ch.read_temp()[0:0]
                            .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                        )
                        del st.session_state["border"]
                        reset()

                elif alt > 1:
                    already = st.checkbox("Ci sono già stato, dimmene un altro")
                    if already:
                        disabled = False
                    else:
                        disabled = True
                    rist_slider = st.select_slider(
                        'Ecco delle alternative in ordine decrescente di punteggio calcolato in base alle recensioni di Google',
                        options=np.arange(1, alt+1, 1), disabled = disabled)
                    n_rist = rist_slider - 1

                    html, chose = markdown_and_save(n_rist, type_of_choice="random")

                    st.markdown(html, unsafe_allow_html=True)
                    ok = st.checkbox("Ok, scelgo questo!")

                    if ok:
                        st.balloons()
                        st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")
                        with open('suggests.csv', 'a', encoding='utf-8') as f:
                            chose.to_csv(f, mode='a', header=f.tell() == 0, encoding='utf-8')
                        df = (
                            ch.read_temp()[0:0]
                            .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                        )
                        del st.session_state["border"]
                        reset()

                if alt == 0:
                    st.write("Nessun consiglio per i criteri ricercati.")


