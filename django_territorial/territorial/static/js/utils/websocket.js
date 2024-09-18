export function setupWebSocket(onMessage) {
    const socket = new WebSocket('ws://' + window.location.host + '/ws/square/');
    socket.binaryType = 'arraybuffer';
    socket.onmessage = onMessage;
    return socket;
}
