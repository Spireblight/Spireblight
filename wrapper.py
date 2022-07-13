from typing import Callable, Coroutine, Optional

import inspect

from twitchio.ext.commands import Context

from logger import logger

__all__ = ["wrapper"]

def wrapper(func: Callable, force_argcount: bool, wrapper_func: Optional[Coroutine], name: Optional[str]):
    if name is None:
        name = func.__name__
    async def caller(ctx: Context, *args: str):
        wrapped_args = None
        if wrapper_func is not None:
            try:
                wrapped_args: list = await wrapper_func(ctx)
            except ValueError:
                return
        new_args = []
        if wrapped_args is not None:
            new_args.extend(wrapped_args)
        multiple = (co.co_flags & 0x04) # whether *args is supported
        annotations = inspect.get_annotations(func, eval_str=True)
        for i, arg in enumerate(args, len(new_args) + 1):
            if i < co.co_argcount:
                var = co.co_varnames[i]
            elif multiple: # all from here on will match the same type -- typically str, but could be something else
                var = co.co_varnames[co.co_argcount]
            else: # no *args and reached max argcount; no point in continuing
                break
            if var in annotations:
                expected = annotations[var]
                if expected == int:
                    try:
                        arg = int(arg)
                    except ValueError:
                        await ctx.send(f"Error: Argument #{i} ({var!r}) must be an integer.")
                        return
                elif expected == float:
                    try:
                        arg = float(arg)
                    except ValueError:
                        await ctx.send(f"Error: Argument #{i} ({var!r}) must be a floating point number.")
                        return
                elif expected == bool:
                    if arg.lower() in ("yes", "y", "on", "true", "1"):
                        arg = True
                    elif arg.lower() in ("no", "n", "off", "false", "0"):
                        arg = False
                    else:
                        await ctx.send(f"Error: Argument #{i} ({var!r}) must be parsable as a boolean value.")
                        return
                elif expected != str:
                    await ctx.send(f"Warning: Unhandled type {expected!r} for argument #{i} ({var!r}) - please ping @FaeLyka")
            new_args.append(arg)

        if req > len(new_args):
            names = co.co_varnames[len(new_args):req]
            if len(names) == 1:
                await ctx.send(f"Error: Missing required argument {names[0]!r}")
            else:
                await ctx.send(f"Error: Missing required arguments {names!r}")
            return
        if multiple: # function supports *args, don't check further
            await func(ctx, *new_args)
            return
        if len(new_args) != len(args) and force_argcount: # too many args and we enforce it
            await ctx.send(f"Error: too many arguments (maximum {co.co_argcount - 1})")
            return
        await func(ctx, *new_args)

    co = func.__code__
    req = co.co_argcount - 1
    if func.__defaults__:
        req -= len(func.__defaults__)

    caller.__required__ = req
    caller.__name__ = name
    caller.__doc__ = func.__doc__

    logger.debug(f"Creating wrapped command {name}")

    return caller
