import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.math.BigInteger;
import java.util.ArrayList;

public class FocusedNative extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(Files.newBufferedWriter(Path.of(args[0]), StandardCharsets.UTF_8))) {
            out.println("PROGRAM " + currentProgram.getName());
            out.println("SHA256 " + currentProgram.getExecutableSHA256());
            out.println("IMAGEBASE " + currentProgram.getImageBase());
            out.println("Focused symbol ranges only; no whole-program auto analysis");
            for (String line : Files.readAllLines(Path.of(args[1]))) {
                String[] fields = line.split("\\t", 4);
                Address address = currentProgram.getImageBase().add(Long.parseLong(fields[0], 16));
                long size = Long.parseLong(fields[1]);
                if (size == 0) continue;
                AddressSet range = new AddressSet(address, address.add(size - 1));
                ArrayList<Address> overlaps = new ArrayList<>();
                var iterator = currentProgram.getFunctionManager().getFunctionsOverlapping(range);
                while (iterator.hasNext()) overlaps.add(iterator.next().getEntryPoint());
                for (Address entry : overlaps) currentProgram.getFunctionManager().removeFunction(entry);
                clearListing(address, address.add(size - 1));
                currentProgram.getProgramContext().setValue(currentProgram.getRegister("TMode"), address, address.add(size - 1), new BigInteger(fields[2]));
                new DisassembleCommand(address, new AddressSet(address, address.add(size - 1)), true).applyTo(currentProgram, monitor);
                Function function = getFunctionAt(address);
                if (function == null) function = createFunction(address, fields[3]);
                if (function != null) function.setBody(new AddressSet(address, address.add(size - 1)));
                out.println("FUNCTION " + address + " size=" + size + " " + fields[3]);
                if (function == null) { out.println("ERROR no function"); continue; }
                decompiler.flushCache();
                DecompileResults result = decompiler.decompileFunction(function, 45, monitor);
                if (result.decompileCompleted()) out.println(result.getDecompiledFunction().getC());
                else out.println("ERROR " + result.getErrorMessage());
                out.flush();
            }
        } finally { decompiler.dispose(); }
    }
}
