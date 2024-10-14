const { useEffect, useRef, createElement } = React;
const { WIDTH: GAME_WIDTH, HEIGHT: GAME_HEIGHT } = window.GAME_CONFIG;

export default function Canvas({ setApp }) {
    const canvasRef = useRef(null);
    const isDragging = useRef(false);
    const lastPosition = useRef({ x: 0, y: 0 });

    useEffect(() => {
        const pixiApp = new PIXI.Application({
            width: GAME_WIDTH,
            height: GAME_HEIGHT,
            backgroundColor: 0xFFFFFF,
            resizeTo: window,
            autoDensity: true,
            resolution: window.devicePixelRatio || 1,
        });
        canvasRef.current.appendChild(pixiApp.view);
        setApp(pixiApp);

        const scalingContainer = new PIXI.Container();
        pixiApp.stage.addChild(scalingContainer);

        const graphics = new PIXI.Graphics();
        scalingContainer.addChild(graphics);

        const textContainer = new PIXI.Container();
        scalingContainer.addChild(textContainer);

        const leaderboardContainer = new PIXI.Container();
        scalingContainer.addChild(leaderboardContainer);

        const boatsContainer = new PIXI.Container();
        scalingContainer.addChild(boatsContainer);

        const resizeHandler = () => {
            const screenWidth = window.innerWidth;
            const screenHeight = window.innerHeight;
            const scale = Math.min(screenWidth / GAME_WIDTH, screenHeight / GAME_HEIGHT);

            scalingContainer.scale.set(scale);
            scalingContainer.position.set(
                (screenWidth - GAME_WIDTH * scale) / 2,
                (screenHeight - GAME_HEIGHT * scale) / 2
            );
        };

        resizeHandler();
        window.addEventListener('resize', resizeHandler);

        // Zoom functionality
        const zoomHandler = (event) => {
            event.preventDefault();
            const zoomFactor = event.deltaY > 0 ? 0.9 : 1.1;

            // Get mouse position relative to the canvas
            const bounds = pixiApp.view.getBoundingClientRect();
            const mouseX = event.clientX - bounds.left;
            const mouseY = event.clientY - bounds.top;

            // Calculate world position before zoom
            const worldPos = scalingContainer.toLocal(new PIXI.Point(mouseX, mouseY));

            // Apply zoom
            scalingContainer.scale.x *= zoomFactor;
            scalingContainer.scale.y *= zoomFactor;

            // Calculate new screen position after zoom
            const newScreenPos = scalingContainer.toGlobal(worldPos);

            // Adjust container position to keep mouse on the same world position
            scalingContainer.position.x -= (newScreenPos.x - mouseX);
            scalingContainer.position.y -= (newScreenPos.y - mouseY);
        };

        // Pan functionality
        const startDrag = (event) => {
            isDragging.current = true;
            lastPosition.current = { x: event.clientX, y: event.clientY };
        };

        const endDrag = () => {
            isDragging.current = false;
        };

        const drag = (event) => {
            if (isDragging.current) {
                const dx = event.clientX - lastPosition.current.x;
                const dy = event.clientY - lastPosition.current.y;
                scalingContainer.position.x += dx;
                scalingContainer.position.y += dy;
                lastPosition.current = { x: event.clientX, y: event.clientY };
            }
        };

        pixiApp.view.addEventListener('wheel', zoomHandler);
        pixiApp.view.addEventListener('mousedown', startDrag);
        pixiApp.view.addEventListener('mouseup', endDrag);
        pixiApp.view.addEventListener('mousemove', drag);

        return () => {
            pixiApp.destroy(true);
            window.removeEventListener('resize', resizeHandler);
            pixiApp.view.removeEventListener('wheel', zoomHandler);
            pixiApp.view.removeEventListener('mousedown', startDrag);
            pixiApp.view.removeEventListener('mouseup', endDrag);
            pixiApp.view.removeEventListener('mousemove', drag);
        };
    }, []);

    return createElement('div', { ref: canvasRef });
}
