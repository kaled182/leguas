document.addEventListener("DOMContentLoaded", function () {
    const map = window._leaflet_map || window.map_1 || null;
    if (!map || !navigator.geolocation) return;

    navigator.geolocation.getCurrentPosition(function (position) {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;

        const marker = L.marker([lat, lon], {
            icon: L.icon({
                iconUrl: 'https://img.icons8.com/fluency/48/marker.png',
                iconSize: [32, 32],
                iconAnchor: [16, 32],
                popupAnchor: [0, -32]
            })
        }).addTo(map);

        marker.bindPopup("Você está aqui").openPopup();
        map.setView([lat, lon], 13);
    });
});
