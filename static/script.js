var gateway = 'ws://192.168.29.44:8765/ws';
var websocket;
var marker;
var longitude;
var latitude;
window.addEventListener('load', onLoad);

function onLoad(event) {
  initWebSocket();
  initButton();
}

function initWebSocket() {
  console.log('Trying to open a WebSocket connection...');
  websocket = new WebSocket(gateway);
  websocket.onopen = onOpen;
  websocket.onclose = onClose;
  websocket.onmessage = onMessage;
}

function onOpen(event) {
  console.log('Connection opened');
}

function onClose(event) {
  console.log('Connection closed');
  setTimeout(initWebSocket, 2000);
}

function showError(error) {
  switch (error.code) {
    case 1:
      locationInfo.innerHTML = "Permission denied";
      break;
    case 2:
      locationInfo.innerHTML = "Position unavailable";
      break;
    case 3:
      locationInfo.innerHTML = "Timeout";
      break;
  }
}

  function onMessage(event) {
  }


function initButton() {
  const buttonLeft = document.getElementById('button');
  const buttonRight = document.getElementById('button2');
  const buttonUp = document.getElementById('button3');
  const buttonDown = document.getElementById('button4');
  const buttonStop = document.getElementById('stopMovement');
  const buttonpanic = document.getElementById('panic');

  let leftIntervalId, rightIntervalId, upIntervalId, downIntervalId;

  buttonLeft.addEventListener("mousedown", () => {
    left();
    leftIntervalId = setInterval(left, 50);
  });

  buttonLeft.addEventListener("mouseup", () => {
    clearInterval(leftIntervalId);
    stop();
  });

  buttonRight.addEventListener("mousedown", () => {
    right();
    rightIntervalId = setInterval(right, 50);
  });

  buttonRight.addEventListener("mouseup", () => {
    clearInterval(rightIntervalId);
    stop();
  });

  buttonUp.addEventListener("mousedown", () => {
    up();
    upIntervalId = setInterval(up, 50);
  });

  buttonUp.addEventListener("mouseup", () => {
    clearInterval(upIntervalId);
    stop();
  });

  buttonDown.addEventListener("mousedown", () => {
    down();
    downIntervalId = setInterval(down, 50);
  });

  buttonDown.addEventListener("mouseup", () => {
    clearInterval(downIntervalId);
    stop();
  });

  buttonStop.addEventListener("click", () => {
    stop();
  });

  buttonpanic.addEventListener("click", () => {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(sendPosition, showError, {
          enableHighAccuracy: true,
          maximumAge: 30000,
          timeout: 27000
        });
      } else {
        console.log("Geolocation is not supported by this browser.");
      }
  });
  

  getLocation.addEventListener("click", () => {
    navigator.geolocation.getCurrentPosition(showPosition,showError, {
      enableHighAccuracy: true,
      maximumAge: 30000,
      timeout: 270000
    });
  });

  function showError(error) {
    switch (error.code) {
      case 1:
        locationInfo.innerHTML = "Permission denied";
        break;
      case 2:
        locationInfo.innerHTML = "Position unavailable";
        break;
      case 3:
        locationInfo.innerHTML = "Timeout";
        break;
    }
  }

   function showPosition(position) {
   latitude = position.coords.latitude;
   longitude = position.coords.longitude;

    


    var map = L.map('mapid').setView([latitude, longitude], 13);


    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors'
    }).addTo(map);


    marker = L.marker([latitude, longitude]).addTo(map)
      .bindPopup(`Latitude: ${latitude}<br>Longitude: ${longitude}`)
      .openPopup();
  }
  
 function left() {
    websocket.send('LEFT');
  }

  function right() {
    websocket.send('RIGHT');
  }

  function up() {
    websocket.send('UP');
  }

  function down() {
    websocket.send('DOWN');
  }

  function stop() {
    websocket.send('STOP');
  }

}

function sendPosition(position) {
  let url = '/location';

  // If position is available, send as a POST request
  if (position) {
      fetch(url, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify({
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
          }),
      })
      .then(response => response.json())
      .then(data => console.log("POST Response:", data))
      .catch(error => console.log("Error sending location:", error));
  } else {
      // If no position argument, send a GET request
      fetch(url, {
          method: 'GET',
          headers: {
              'Content-Type': 'application/json',
          },
      })
      .then(response => response.json())
      .then(data => {
          if (data.latitude && data.longitude) {
              console.log(`GET Response: Latitude = ${data.latitude}, Longitude = ${data.longitude}`);
          } else {
              console.log("Error retrieving geolocation:", data.error);
          }
      })
      .catch(error => console.log("Error getting location:", error));
  }
}


