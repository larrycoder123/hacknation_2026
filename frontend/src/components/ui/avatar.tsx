import * as React from "react"
import { cn } from "@/lib/utils"

export interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
    src?: string | null
    alt?: string
    fallback?: string
}

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
    ({ className, src, alt, fallback, ...props }, ref) => {
        // Determine fallback text
        const fallbackText = fallback || (alt ? alt.slice(0, 2).toUpperCase() : "?");

        return (
            <div
                ref={ref}
                className={cn(
                    "relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full bg-muted",
                    className
                )}
                {...props}
            >
                {src ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                        src={src}
                        alt={alt || ""}
                        className="aspect-square h-full w-full object-cover"
                    />
                ) : (
                    <div className="flex h-full w-full items-center justify-center rounded-full bg-muted text-muted-foreground font-medium text-xs">
                        {fallbackText}
                    </div>
                )}
            </div>
        )
    }
)
Avatar.displayName = "Avatar"

export { Avatar }
