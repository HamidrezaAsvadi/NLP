// script.js
// List of northern Italian cities with coordinates
const cities = [
  { name: "Bolzano", lat: 46.4983, lon: 11.3548, highlight: true },
  { name: "Trento", lat: 46.0679, lon: 11.1217 },
  { name: "Verona", lat: 45.4384, lon: 10.9916 },
  { name: "Milan", lat: 45.4642, lon: 9.1900 },
  { name: "Bergamo", lat: 45.6983, lon: 9.6773 },
  { name: "Vicenza", lat: 45.5469, lon: 11.5475 },
  { name: "Udine", lat: 46.0679, lon: 13.2365 }
];

const container = document.getElementById("city-container");

function createCard(city) {
  const card = document.createElement("div");
  card.className = "city-card" + (city.highlight ? " highlight" : "");

  const name = document.createElement("div");
  name.className = "city-name";
  name.textContent = city.name;
  card.appendChild(name);

  const temp = document.createElement("div");
  temp.className = "temperature";
  temp.textContent = "--°C";
  card.appendChild(temp);

  const time = document.createElement("div");
  time.className = "updated-time";
  time.textContent = "";
  card.appendChild(time);

  // Attach to city object for later updates
  city._elements = { temp, time };
  container.appendChild(card);
}

function updateCityWeather(city) {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${city.lat}&longitude=${city.lon}&current_weather=true`;
  fetch(url)
    .then((res) => res.json())
    .then((data) => {
      if (data.current_weather) {
        const temperature = data.current_weather.temperature;
        const time = new Date(data.current_weather.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        city._elements.temp.textContent = `${temperature.toFixed(1)}°C`;
        city._elements.time.textContent = `Updated ${time}`;
      } else {
        city._elements.temp.textContent = "N/A";
      }
    })
    .catch(() => {
      city._elements.temp.textContent = "Error";
    });
}

function init() {
  // Create cards
  cities.forEach(createCard);
  // Initial fetch
  cities.forEach(updateCityWeather);
  // Refresh every 60 seconds
  setInterval(() => {
    cities.forEach(updateCityWeather);
  }, 60000);
}

// Start when DOM is ready
if (document.readyState !== "loading") {
  init();
} else {
  document.addEventListener("DOMContentLoaded", init);
}
