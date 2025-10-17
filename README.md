# Diyoloji: Kurumsal Yanıt Asistanı

**Diyoloji**, kurumların dijital platformlardaki müşteri geri bildirimlerine **empatik, bağlamsal ve doğru** yanıtlar üretebilen bir **Yapay Zeka Destekli Kurumsal Yanıt Asistanıdır**.  
Proje, Turkcell gibi büyük ölçekli ya da küçük ölçekli kurumlar için sosyal medya, destek sayfaları ve müşteri iletişim kanallarındaki mesajları anlayıp otomatik olarak uygun yanıtlar oluşturmayı amaçlar.

**Live Demo:** [https://diyoloji-10185413429.europe-west3.run.app/](https://diyoloji-10185413429.europe-west3.run.app/)

## Projenin Amacı

- Müşteri geri bildirimlerini **doğal dil işleme (NLP)** teknikleriyle analiz eder.  
- Geri bildirimin duygusal tonunu (pozitif / negatif / nötr) ve kategorisini (fatura, paket, roaming vb.) belirler.  
- Şirketin bilgi tabanında yer alan belgelerden (Turkcell destek sayfaları gibi) **en alakalı içerikleri** arar.  
- **Empatik ve aksiyona yönlendiren yanıtlar** üretir.  
- Gerektiğinde otomatik olarak **X (Twitter)** üzerinden müşteri geri bildirimlerine yanıt gönderir.

## Genel Yapı  
Proje; veri toplama, vektör arama, RAG tabanlı yanıt üretimi ve sosyal medya otomasyonu modüllerinden oluşmaktadır.

Bu yapı, projenin hem **backend (FastAPI + RAG)** kısmını hem de **otomasyon (RPA)** modülünü içermektedir.  
`src/` klasörü asıl uygulama mantığını barındırırken, `turkcell_crawler/` dizini Turkcell destek sayfalarını JSONL formatında bilgi tabanına dönüştürmek için kullanılır.

## Çekirdek Bileşenler

| Modül | Açıklama |
|--------|-----------|
| **config.py** | OpenAI, Milvus, LangSmith ve sunucu yapılandırmalarını yönetir. |
| **embeddings.py** | OpenAI Embedding API’sini kullanarak metinleri vektörleştirir. |
| **vector_milvus.py** | Milvus veritabanında embedding tabanlı arama ve indeksleme işlemlerini yapar. |
| **rag.py** | Kullanıcı sorgusunu işler, intent/sentiment sınıflandırması yapar ve uygun cevabı üretir. |
| **server.py** | FastAPI ile REST API ve web arayüzünü sunar. |
| **rpa.py** | X (Twitter) üzerinde belirlenen hesaplara otomatik olarak yanıt gönderir. |
| **turkcell_crawler/** | Turkcell destek sayfalarını crawl ederek bilgi tabanı (JSONL) üretir. |


## Kurulum ve Çalıştırma

### Ortamı Hazırlayın
cp .env.example .env


pip install -r requirements.txt

### OpenAI ve Milvus Bilgilerini .env Dosyasına Ekleyin

OPENAI_API_KEY=sk-************


MILVUS_URI=xxxx.zillizcloud.com


MILVUS_TOKEN=your_zilliz_token


MILVUS_COLLECTION=diyoloji_docs

### Veri Yükleme (Ingest)
python -m src.server ingest --file data/db_turkcell.jsonl

### Sunucuyu Başlatın
python -m uvicorn src.server:app --reload --host 127.0.0.1 --port 8000


Ardından tarayıcıda açın:


http://127.0.0.1:8000

veya canlı sürüm:


https://diyoloji-10185413429.europe-west3.run.app/

### Diyoloji'yi Deneyin
python -m src.server ask "Paketim bitti, ne yapmalıyım?" --tool package

### RPA (X / Twitter Otomasyon)
Diyoloji, gerçek zamanlı sosyal medya yanıtlarını Selenium tabanlı RPA ile otomatikleştirir.
src/rpa.py dosyası, Twitter’da belirlenen bir hesabın paylaşımlarını tespit edip yanıt üretir.

Güncellemeniz Gereken Alan(rpa.py):
TARGET_HANDLE = "target_X_username"  # Hedef Twitter kullanıcısını giriniz.

Çalıştırmak için:
python -m src.rpa

### Değerlendirme (Evaluation)

Oluşturulan yanıtların doğruluğunu ölçmek için:

python -m src.eval_rag --file data/eval_dataset.json


### Crawler: Turkcell Destek Sayfaları

turkcell_crawler/ dizini, Turkcell’in destek sayfalarındaki verileri otomatik olarak toplar.
Her crawler script’i farklı bir kategoriye (örneğin Yurtdışı, Paket, Cihaz) odaklanır. 

Crawler ihtiyaç halinde farklı kurumların web sayfaları ile güncellenerek yeni veriler toplanabilir ve güncellenebilir.


### LangSmith Log ve Performans İzleme

Projeye gelen tüm istekler, LangSmith Log ekranı üzerinden takip edilmektedir.
İlgili proje bağlantısı: https://eu.smith.langchain.com/o/b0d1345a-64df-4e4b-932e-e6a7f89f5432/projects/p/b9ec5a8b-a775-473e-88c4-b822edc6e052?timeModel=%7B"duration"%3A"7d"%7D

LangSmith, uygulamamızın LLM tabanlı pipeline performansını uçtan uca gözlemlememize olanak sağlar. Bu platform üzerinden:
	•	İstek Geçmişi (Request Logs): Her bir kullanıcı isteği detaylı şekilde kaydedilir. Böylece hangi sorguların işlendiğini, hangi araçların (tools) çağrıldığını ve hangi yanıtların üretildiğini adım adım görebiliriz.
	•	Yanıt Süresi (Latency): Her istek için ortalama yanıt süresi ölçülür. Bu metrik, sistemin ölçeklenebilirliği ve kullanıcı deneyimi açısından kritik öneme sahiptir.
	•	Token Kullanımı (Prompt / Completion Tokens): LLM çağrılarında harcanan toplam token miktarı takip edilir. Bu sayede maliyet optimizasyonu yapılabilir ve gereksiz token tüketimi önlenir.
	•	Başarı Oranı (Success Rate): Yanıt üretilen toplam istekler arasındaki başarılı yürütme oranı izlenir. Olası hata veya başarısız sorgular anında tespit edilip analiz edilir.
	•	Tool Çağrıları ve Performans: REACT agent mimarisinde kullanılan araçların çağrılma sıklığı, yanıt süreleri ve hata oranları gözlemlenir. Bu bilgiler, hangi tool’un darboğaz oluşturduğunu anlamamızı sağlar.




## Lisans

Bu proje, araştırma ve eğitim amaçlı olarak geliştirilmiştir.
Ticari kullanım için izin alınması gereklidir.


### Hızlı Başlangıç
1) `cp .env.example .env` ve değerleri doldur.
2) `pip install -r requirements.txt`
3) İndeks oluştur: `python -m src.server ingest`
4) Soru sor: `python -m src.server ask "Paketim bitti ne yapmalıyım?" --tool package`


### Değişkende Ne Var?
- OpenAI: `gpt-4o-mini` (chat) + `text-embedding-3-small` (embed)
- Milvus: `MILVUS_URI`, `MILVUS_COLLECTION`, `MILVUS_DIM`


### Eval
- `python -m src.eval ./eval_dataset.csv`
