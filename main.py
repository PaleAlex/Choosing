#imports
from choosing import *
import streamlit as st
from PIL import Image
import os
from datetime import date, timedelta
import re


st.set_page_config(layout="wide")
image = Image.open('logo.png')

st.image(image, width=450)
bucket = bucket

#inputs

st.sidebar.header('User Input')

def check(s):
    pat = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    if re.match(pat,s):
        return s
    else:
        return None

username = st.sidebar.text_input('Identificati con una tua mail (non sarà visibile agli altri utenti)', placeholder="e.g. iamcool@coolest.it" )

if not username:
    st.markdown("""
<div style = "text-align: justify;">

# Cos'è Choosing?

La sua missione unica e imprescindibile è quella di generare un consiglio personalizzato per il tuo prossimo ristorante.
Finalmente, non dovrai più scrivere a Pippo  *"Oh Pippo sono a Roma, dimmi dove posso andare a mangiare un'ottima pizza*", perchè la risposta te la da Choosing, che è molto più disponibile e preciso di Pippo.
E basta anche con tutto quel tempo speso davanti ai siti di recensioni a contare le stelline e a confrontare prezzi e numero di commenti delle infinite alternative per poi
finire a mangiare nella solita osteria.

Dedica il tuo tempo alle cose migliori. A sceglierle ci pensa Choosing.

Enjoy the perfect meal.


## Come funziona?

Choosing usa due strategie alternative:
                
 1. Ricerca per similarità tra gli utenti di Choosing in base ai ristoranti in comune e ai rating assegnati

 2. Qualora 1. non restituisca un risultato, Choosing sceglie il ristorante migliore basandosi sulle recensioni di Google

Il consiglio che deriva da 1. è molto più personalizzato rispetto a quello di 2. ed è il vero orgoglio di Choosing. L'unica condizione affinché si verifichi è la partecipazione attiva di tanti utenti e il passaparola, se credi nei superpoteri di Choosing.

Per cominciare, identificati con una mail nel menù a sinistra e buon appetito :)


## Feedback

Per suggerimenti o per rimanere semplicemente in contatto scrivimi a aless.ciocchetti@gmail.com


## Support

Mantenere e migliorare Choosing ha qualche costo (APIs, server...).

Se credi che Choosing sia una bella e utile idea, puoi sostenerla con una piccola donazione qua: [Buy me a coffee](https://www.buymeacoffee.com/palealex)


## Author

- [Alessandro Ciocchetti](https://www.linkedin.com/in/ac-palealex/)


## 🚀 About Me
Gestisco il mio tempo tra tentativi di scrivere qualcosa che somigli a bel codice, di sviluppare idee che ricordino grandi progetti, di suonare l'armonica come la suonava Paul Butterfield.

Lo sviluppo web e lo studio delle proprietà delle Serie Temporali mi divertono particolarmente.

</div>

""", unsafe_allow_html=True)

elif not check(username): #and username != config.root:
    st.warning('Email non valida', icon="⚠️")

#elif username == config.root:
#    with open('final.csv') as f:
#        st.download_button('final', f, mime='text/csv')
#    with open('suggests.csv') as f:
#        st.download_button('suggests', f, mime='text/csv')
#    canc = st.checkbox("cancella file temporanei")
#    mydir = "user_temps/"
#    filelist = [ f for f in os.listdir(mydir) if f.endswith(".csv") ]
#    st.write("numero file temporanei esistenti ", len(filelist))
#    to_delete = st.multiselect('Delete', filelist, filelist)

#    if canc:
#        for f in to_delete:
#            os.remove(os.path.join(mydir, f))
#            st.write(f)
    #mettere anche funzione per cancellare da final delle righe di utenti sbagliati per esempio (deve diventare dashboard di controllo)

else:
    with st.sidebar:
        meal = st.multiselect('Cosa vuoi mangiare?', ("Primi piatti", "Pizza", "Street food", "Carne", "Pesce", "Vegetariano/Vegano", "Etnico", "Orientale", "Altro"), ("Primi piatti", "Pizza", "Street food", "Carne", "Pesce", "Vegetariano/Vegano", "Etnico", "Orientale", "Altro"), help="Utile solo nel caso di ricerca per similarità con altri utenti")
        city = st.text_input('Città', placeholder="e.g. Ferrara", key = "field").capitalize()
        province = st.text_input('Provincia (sigla)', placeholder="e.g. FE", max_chars=2).upper()
        state = st.text_input('Stato', placeholder="e.g. Italia").capitalize()
        border = st.selectbox("Confine di ricerca", ("comune", "provincia"))
        epp = st.slider("Range spesa per persona", 1, 100, (15, 50), help="Utile solo nel caso di ricerca per similarità con altri utenti")

    if "border" not in st.session_state:
        st.session_state["border"] = border
    if "geo" not in st.session_state:
        st.session_state["geo"] = (city, province)

    if not meal or not city or not province or not state:
        st.write("*Per conoscere il tuo prossimo miglior ristorante, compila tutti i campi del menù laterale. Se invece devi ancora valutare un ristorante in cui sei stato, continua prima qui sotto*")

        #reviewing

        container1 = st.expander("VEDI I RISTORANTI A CUI POTRESTI LASCIARE UNA VALUTAZIONE")
        with container1:
            def user_to_review():
                data = pd.read_csv(
                    io.BytesIO(
                        bucket.blob(blob_name = "suggests.csv").download_as_bytes()
                    ),
                    index_col = 0, encoding = 'utf-8'
                )
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
                    filename = "final.csv"
                    UPLOADFILE = os.path.join(os.getcwd(),filename)
                    blob = bucket.blob(filename)
                    blob.upload_from_filename(UPLOADFILE)

                    tendaysago = date.today() - timedelta(10)

                    suggests = pd.read_csv(
                        io.BytesIO(
                            bucket.blob(blob_name = "suggests.csv").download_as_bytes()
                        ),
                        index_col = 0, encoding = 'utf-8'
                    ).reset_index(drop=True)

                    suggests["added"] = pd.to_datetime(suggests["added"], format='%Y-%m-%d').dt.date

                    try:
                        suggests.drop(suggests.index[(suggests['name'] == reviewed['name'][0]) & (suggests['user'] == reviewed['user'][0])], inplace=True)
                    except:
                        pass
                    suggests = suggests[suggests["added"] > tendaysago].reset_index(drop=True)
                    suggests.to_csv("suggests.csv")
                    filename = "suggests.csv"
                    UPLOADFILE = os.path.join(os.getcwd(),filename)
                    blob = bucket.blob(filename)
                    blob.upload_from_filename(UPLOADFILE)

                    final = pd.read_csv(
                        io.BytesIO(
                            bucket.blob(blob_name = "final.csv").download_as_bytes()
                        ),
                        index_col = 0, encoding = 'utf-8'
                    ).drop_duplicates(subset=["name", "user", "what"], keep = 'last').reset_index(drop=True)

                    final.to_csv("final.csv")
                    filename = "final.csv"
                    UPLOADFILE = os.path.join(os.getcwd(),filename)
                    blob = bucket.blob(filename)
                    blob.upload_from_filename(UPLOADFILE)

                    st.experimental_rerun()

            else:
                st.write("Non hai nessun ristorante salvato da valutare. Scegline prima uno e, dopo averlo provato, torna qua a valutarlo.")

        container2 = st.expander("VEDI I RISTORANTI A CUI HAI LASCIATO UNA VALUTAZIONE")
        with container2:
            def user_reviewed():
                data = pd.read_csv(
                    io.BytesIO(
                        bucket.blob(blob_name = "final.csv").download_as_bytes()
                    ),
                    index_col = 0, encoding = 'utf-8'
                )
                return data[data["user"] == username].drop_duplicates(keep= 'last').reset_index(drop= True)

            if len(user_reviewed()) > 0:
                to_be_reviewed = user_reviewed()
                st.dataframe(data=to_be_reviewed.iloc[:, [0,1,3,5,6,7]])
            else:
                st.write("Non hai ancora lasciato nessuna valutazione.")
    else:
        #choosing object
        ch = Choosing(username, meal, city, province, state, epp, border)
        if border != st.session_state["border"] or (city, province) != st.session_state["geo"]:
            df = (
                ch.read_temp()[0:0]
                .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
            )
            filename = f"user_temps/temp_{username}.csv"
            UPLOADFILE = os.path.join(os.getcwd(),filename)
            blob = bucket.blob(filename)
            blob.upload_from_filename(UPLOADFILE)

            st.session_state["border"] = border
            st.session_state["geo"] = (city, province)

        #suggests

        container = st.expander("TI SVELO IL TUO PROSSIMO MIGLIOR RISTORANTE")
        with container:
            #---------------------------------------------------------------------
            def markdown_and_save(n_rist, type_of_choice):
                if type_of_choice == 'matched':
                    chose = ch.matched_choice(choice = n_rist)
                    st.markdown('''
                        ******Trovato :tada: ! In base al match con gli altri utenti:******
                        
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
                    form = st.form(key="case1", clear_on_submit = True)
                    with form:
                        ok = st.checkbox("Ok, scelgo questo!")
                    submit = form.form_submit_button("Salva")
                    if submit:
                        st.balloons()
                        st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")
                        with open('suggests.csv', 'a', encoding='utf-8') as f:
                            chose.to_csv(f, mode='a', header=f.tell() == 0, encoding='utf-8')
                        filename = "suggests.csv"
                        UPLOADFILE = os.path.join(os.getcwd(),filename)
                        blob = bucket.blob(filename)
                        blob.upload_from_filename(UPLOADFILE)

                        df = (
                            ch.read_temp()[0:0]
                            .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                        )
                        filename = f"user_temps/temp_{username}.csv"
                        UPLOADFILE = os.path.join(os.getcwd(),filename)
                        blob = bucket.blob(filename)
                        blob.upload_from_filename(UPLOADFILE)

                        del st.session_state["border"]
                        del st.session_state["geo"]

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
                    form = st.form(key="case2", clear_on_submit = True)
                    with form:
                        ok = st.checkbox("Ok, scelgo questo!")
                    submit = form.form_submit_button("Salva")
                    if submit:
                        st.balloons()
                        st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")
                        with open('suggests.csv', 'a', encoding='utf-8') as f:
                            chose.to_csv(f, mode='a', header=f.tell() == 0, encoding='utf-8')
                        filename = "suggests.csv"
                        UPLOADFILE = os.path.join(os.getcwd(),filename)
                        blob = bucket.blob(filename)
                        blob.upload_from_filename(UPLOADFILE)

                        df = (
                            ch.read_temp()[0:0]
                            .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                        )
                        filename = f"user_temps/temp_{username}.csv"
                        UPLOADFILE = os.path.join(os.getcwd(),filename)
                        blob = bucket.blob(filename)
                        blob.upload_from_filename(UPLOADFILE)

                        del st.session_state["border"]
                        del st.session_state["geo"]

                else:
                    raise Exception("...")

            except:
                alt = len(ch.random_restaurants())

                if alt == 1:
                    n_rist = 0
                    html, chose = markdown_and_save(n_rist, type_of_choice="random")
                    st.markdown(html, unsafe_allow_html=True)

                    form = st.form(key="case3", clear_on_submit = True)
                    with form:
                        ok = st.checkbox("Ok, scelgo questo!")
                    submit = form.form_submit_button("Salva")
                    if submit:
                        st.balloons()
                        st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")
                        with open('suggests.csv', 'a', encoding='utf-8') as f:
                            chose.to_csv(f, mode='a', header=f.tell() == 0, encoding='utf-8')
                        filename = "suggests.csv"
                        UPLOADFILE = os.path.join(os.getcwd(),filename)
                        blob = bucket.blob(filename)
                        blob.upload_from_filename(UPLOADFILE)

                        df = (
                            ch.read_temp()[0:0]
                            .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                        )
                        filename = f"user_temps/temp_{username}.csv"
                        UPLOADFILE = os.path.join(os.getcwd(),filename)
                        blob = bucket.blob(filename)
                        blob.upload_from_filename(UPLOADFILE)

                        del st.session_state["border"]
                        del st.session_state["geo"]

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

                    form = st.form(key="case4", clear_on_submit = True)
                    with form:
                        ok = st.checkbox("Ok, scelgo questo!")
                    submit = form.form_submit_button("Salva")
                    if submit:
                        st.balloons()
                        st.success("Ristorante registrato a tuo nome. Ottima scelta e buon appetito! Ricordati poi di tornare qua a dargli un voto", icon = "✅")
                        with open('suggests.csv', 'a', encoding='utf-8') as f:
                            chose.to_csv(f, mode='a', header=f.tell() == 0, encoding='utf-8')
                        filename = "suggests.csv"
                        UPLOADFILE = os.path.join(os.getcwd(),filename)
                        blob = bucket.blob(filename)
                        blob.upload_from_filename(UPLOADFILE)

                        df = (
                            ch.read_temp()[0:0]
                            .to_csv(f"user_temps/temp_{username}.csv", encoding='utf-8')
                        )
                        filename = f"user_temps/temp_{username}.csv"
                        UPLOADFILE = os.path.join(os.getcwd(),filename)
                        blob = bucket.blob(filename)
                        blob.upload_from_filename(UPLOADFILE)

                        del st.session_state["border"]
                        del st.session_state["geo"]

                if alt == 0:
                    st.write("Nessun consiglio per i criteri ricercati.")


