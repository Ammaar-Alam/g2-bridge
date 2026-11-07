import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Pattern;

public class InspectTransport extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        Pattern pattern = Pattern.compile(args[1], Pattern.CASE_INSENSITIVE);
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(Files.newBufferedWriter(Path.of(args[0]), StandardCharsets.UTF_8))) {
            out.println("PROGRAM " + currentProgram.getName());
            out.println("LANGUAGE " + currentProgram.getLanguageID());
            out.println("SHA256 " + currentProgram.getExecutableSHA256());
            for (Function function : currentProgram.getFunctionManager().getFunctions(true)) {
                out.println("FUNCTION " + function.getEntryPoint() + " " + function.getName(true));
                if (!function.isExternal() && (pattern.matcher(function.getName(true)).find() || pattern.matcher(function.getEntryPoint().toString()).matches())) {
                    DecompileResults result = decompiler.decompileFunction(function, 45, monitor);
                    out.println("DECOMPILE " + function.getEntryPoint() + " " + function.getName(true));
                    if (result.decompileCompleted()) out.println(result.getDecompiledFunction().getC());
                    else out.println("ERROR " + result.getErrorMessage());
                    out.flush();
                }
            }
        } finally { decompiler.dispose(); }
    }
}
