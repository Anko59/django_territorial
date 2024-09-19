const { useEffect, useRef, createElement } = React;

export default function Canvas({ setApp }) {
    const canvasRef = useRef(null);

    useEffect(() => {
        const pixiApp = new PIXI.Application({
            width: 600,
            height: 400,
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

        const resizeHandler = () => {
            const screenWidth = window.innerWidth;
            const screenHeight = window.innerHeight;
            const scale = Math.min(screenWidth / 600, screenHeight / 400);

            scalingContainer.scale.set(scale);
            scalingContainer.position.set(
                (screenWidth - 600 * scale) / 2,
                (screenHeight - 400 * scale) / 2
            );
        };

        resizeHandler();
        window.addEventListener('resize', resizeHandler);

        return () => {
            pixiApp.destroy(true);
            window.removeEventListener('resize', resizeHandler);
        };
    }, []);

    return createElement('div', { ref: canvasRef });
}
