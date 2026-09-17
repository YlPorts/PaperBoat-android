package dev.net64.paperboat

import android.content.Context
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.util.zip.ZipInputStream

/**
 * Everything the game needs on disk, and how it gets there.
 *
 * libultraship resolves every runtime path through
 * `SDL_AndroidGetExternalStoragePath()` — `getExternalFilesDir(null)`, which a
 * file manager can also reach, so mods can be dropped in. Everything lives there:
 *
 *     Android/data/dev.net64.paperboat/files/
 *       baserom.us.z64       the user's ROM, copied in by the launcher
 *       config.yml, assets/  Torch's extraction recipes, unpacked from the APK
 *       paperboat.o2r        engine assets, built from port/ into the APK
 *       pm64.o2r             generated on-device from the ROM
 *       mods/                user mods (.o2r, .zip or plain folders)
 *       saves/               fileN.json, one per save slot
 *
 * Unpacking happens here, not in the engine: Torch needs config.yml and assets/
 * on disk before the game process starts. The zip is built by build.gradle.kts.
 */
object GameAssets {

    // Matches the engine's mobile fallback (GameExtractor.cpp), so an
    // in-game re-extraction finds it too. Torch hashes contents, not the name.
    const val ROM_NAME = "baserom.us.z64"

    private const val TAG = "GameAssets"
    private const val GAME_ARCHIVE = "pm64.o2r"
    private const val GAME_ARCHIVE_READY = ".pm64.o2r.ready"
    private const val CONTROLLER_DB = "gamecontrollerdb.txt"
    private const val TORCH_HASHES = "torch.hash.yml"
    private const val GAMEDATA_ZIP = "gamedata.zip"
    private const val GAMEDATA_VERSION = "gamedata.version"
    private const val STAMP = ".gamedata.version"

    fun gameDir(context: Context): File =
        (context.getExternalFilesDir(null) ?: context.filesDir).also { it.mkdirs() }

    fun romFile(context: Context) = File(gameDir(context), ROM_NAME)

    fun gameArchive(context: Context) = File(gameDir(context), GAME_ARCHIVE)

    private fun gameArchiveReadyMarker(context: Context) = File(gameDir(context), GAME_ARCHIVE_READY)

    fun modsDir(context: Context) = File(gameDir(context), "mods")

    /**
     * An archive is usable only after the native extractor returned normally and
     * the launcher wrote a completion marker containing its final byte length.
     * A process kill/native crash can leave a non-empty pm64.o2r behind, so
     * existence alone is deliberately not enough.
     */
    fun isExtracted(context: Context): Boolean {
        val archive = gameArchive(context)
        val marker = gameArchiveReadyMarker(context)
        if (!archive.isFile || archive.length() <= 0L || !marker.isFile) return false

        val completedLength = runCatching { marker.readText().trim().toLong() }.getOrNull() ?: return false
        return completedLength == archive.length()
    }

    /** Remove generated state so the next extraction always starts cleanly. */
    fun invalidateGeneratedArchive(context: Context) {
        gameArchiveReadyMarker(context).delete()
        gameArchive(context).delete()
        File(gameDir(context), TORCH_HASHES).delete()
    }

    /**
     * Unpacks the APK-bundled extraction inputs into [gameDir]. Re-runs whenever
     * the packaged zip changes, so an update ships new recipes without the user
     * clearing data. Returns an error message, or null when ready.
     */
    fun stageBundledAssets(context: Context): String? {
        val target = gameDir(context)
        val stamp = File(target, STAMP)

        return try {
            val expected = context.assets.open(GAMEDATA_VERSION).use { it.readBytes().decodeToString() }
            if (stamp.takeIf { it.isFile }?.readText() == expected) {
                return null
            }

            context.assets.open(GAMEDATA_ZIP).use { input ->
                ZipInputStream(input.buffered()).use { zip ->
                    while (true) {
                        val entry = zip.nextEntry ?: break
                        val destination = File(target, entry.name).canonicalFile

                        // An entry named ../../x would escape the game directory.
                        if (!destination.path.startsWith(target.canonicalPath + File.separator)) {
                            Log.w(TAG, "Skipping suspicious zip entry ${entry.name}")
                            zip.closeEntry()
                            continue
                        }

                        if (entry.isDirectory) {
                            destination.mkdirs()
                        } else {
                            destination.parentFile?.mkdirs()
                            FileOutputStream(destination).use { output -> zip.copyTo(output, COPY_BUFFER_BYTES) }
                        }
                        zip.closeEntry()
                    }
                }
            }

            // Users are meant to edit this one, so only seed it once.
            val controllerDb = File(target, CONTROLLER_DB)
            if (!controllerDb.isFile) {
                copyAsset(context, CONTROLLER_DB, controllerDb)
            }

            val mods = modsDir(context)
            mods.mkdirs()
            if (mods.list().isNullOrEmpty()) {
                // Only a hint; nothing reads it back, so it must not fail here.
                try {
                    copyAsset(context, "mods/place_mods_here.txt", File(mods, "place_mods_here.txt"))
                } catch (error: IOException) {
                    Log.w(TAG, "Could not write the mods placeholder", error)
                }
            }

            // New recipes make the previous archive stale, and Torch skips
            // work whose inputs it believes are unchanged.
            invalidateGeneratedArchive(context)

            stamp.writeText(expected)
            null
        } catch (error: IOException) {
            Log.e(TAG, "Could not unpack the bundled assets", error)
            "Could not unpack the bundled game files: ${error.message}"
        }
    }

    /**
     * The name Torch knows this ROM by, or null if the recipes don't support it.
     * Answered by the engine from the same config.yml the extraction reads, so
     * the launcher carries no second list of hashes to drift out of sync.
     *
     * [stageBundledAssets] must have run first; it puts config.yml in place.
     */
    fun identifyRom(context: Context, rom: File): String? =
        nativeDetectRom(rom.absolutePath, gameDir(context).absolutePath)

    /**
     * Runs Torch over [romFile] to produce pm64.o2r. Blocking and slow. The
     * ready marker is written only after native extraction returned successfully,
     * which makes an interrupted extraction recoverable on the next launch.
     */
    fun generateGameArchive(context: Context): String? {
        val dir = gameDir(context)
        val archive = gameArchive(context)
        val readyMarker = gameArchiveReadyMarker(context)

        // Never let Torch continue from an archive left by a killed process.
        invalidateGeneratedArchive(context)
        Log.i(TAG, "Starting ROM asset extraction")

        val nativeError = try {
            nativeGenerateGameArchive(romFile(context).absolutePath, dir.absolutePath, dir.absolutePath)
        } catch (error: Throwable) {
            Log.e(TAG, "ROM asset extraction threw before completion", error)
            invalidateGeneratedArchive(context)
            return "Could not extract the ROM assets: ${error.message ?: error.javaClass.simpleName}"
        }

        if (nativeError != null) {
            Log.e(TAG, "ROM asset extraction failed: $nativeError")
            invalidateGeneratedArchive(context)
            return nativeError
        }

        if (!archive.isFile || archive.length() <= 0L) {
            invalidateGeneratedArchive(context)
            return "The extractor finished without producing a usable $GAME_ARCHIVE."
        }

        return try {
            // Persist the exact finished size; isExtracted() rejects a later
            // truncated/replaced archive even if it is still non-empty.
            readyMarker.writeText(archive.length().toString())
            Log.i(TAG, "ROM asset extraction completed (${archive.length()} bytes)")
            null
        } catch (error: IOException) {
            Log.e(TAG, "Could not mark the generated archive complete", error)
            invalidateGeneratedArchive(context)
            "The ROM assets were generated, but their completion marker could not be saved: ${error.message}"
        }
    }

    private const val COPY_BUFFER_BYTES = 1 shl 17

    private fun copyAsset(context: Context, assetPath: String, target: File) {
        target.parentFile?.mkdirs()
        context.assets.open(assetPath).use { input ->
            FileOutputStream(target).use { output ->
                input.copyTo(output)
                output.fd.sync()
            }
        }
    }

    private external fun nativeDetectRom(rom: String, sourceDir: String): String?

    private external fun nativeGenerateGameArchive(rom: String, sourceDir: String, destDir: String): String?

    init {
        // libmain.so carries both the game and the Torch extractor.
        System.loadLibrary("SDL2")
        System.loadLibrary("main")
    }
}
